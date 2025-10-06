# pylint: disable=no-member,broad-except-clause
"""
This module provides a client class for interacting with all required Google APIs,
including Google Gemini for AI-powered cleaning and Google Custom Search for
web lookups.
"""
import os
import json
from typing import Optional, List, Dict, Any

import google.generativeai as genai
from google.api_core import exceptions as google_exceptions
import requests
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from src.core.data_model import ApiConfig


class GoogleApiClient:
    """A client to manage interactions with Google APIs."""

    def __init__(self, api_config: ApiConfig, model_name: Optional[str] = None):
        self.api_config = api_config
        self.gemini_model = None
        self.search_service = None
        self._configure_clients(model_name)

    def _configure_clients(self, model_name: Optional[str]):
        """Initializes the API clients based on the provided keys."""
        if self.api_config.gemini_api_key:
            try:
                genai.configure(api_key=self.api_config.gemini_api_key)
                if model_name:
                    self.gemini_model = genai.GenerativeModel(model_name)
            except Exception as e:
                print(f"Error configuring Gemini API: {e}")

        if self.api_config.search_api_key:
            try:
                self.search_service = build("customsearch", "v1", developerKey=self.api_config.search_api_key)
            except HttpError as e:
                print(f"Error configuring Search API: {e}")

    @staticmethod
    def validate_and_list_models(api_key: str) -> Optional[List[str]]:
        """
        Validates a Gemini API key by listing available 'flash' models.
        Returns a list of model names on success, None on failure.
        """
        try:
            genai.configure(api_key=api_key)
            models = []
            for m in genai.list_models():
                if 'generateContent' in m.supported_generation_methods and 'flash' in m.name:
                    models.append(m.name)
            return models
        except (google_exceptions.PermissionDenied, google_exceptions.Unauthenticated, ValueError) as e:
            print(f"Gemini API Key validation failed: {e}")
            return None
        except Exception as e:
            print(f"An unexpected error occurred during model listing: {e}")
            return None

    def clean_merchant_name(self, raw_name: str) -> Optional[Dict[str, Any]]:
        """Uses a hybrid of regex and AI to clean and standardize a merchant name."""
        import re
        if not self.gemini_model:
            raise ConnectionError("Gemini model is not configured. Check API key and model selection.")
        if not raw_name or not raw_name.strip():
            return {"cleaned_name": "", "reasoning": "Input was empty."}

        # Step 1: Deterministic cleaning with Python's regex
        # Remove leading numbers, special characters (*, @), and spaces.
        pre_processed_name = re.sub(r'^[0-9\s*@]+', '', raw_name).strip()

        # Step 2: Use a more focused AI prompt on the pre-processed string.
        prompt = f"""
        From the merchant string "{pre_processed_name}", extract only the core business name.
        - Ignore location indicators like "COLON ROPA", "TOLUCA", "GUAD 1", "DE JULIO".
        - Extract the primary brand name.

        Examples:
        - Input: "FAMSA COLON ROPA" -> Output: {{"cleaned_name": "FAMSA", "reasoning": "Extracted brand name 'FAMSA' and ignored location."}}
        - Input: "MPROMODA TOLUCA" -> Output: {{"cleaned_name": "MPROMODA", "reasoning": "Extracted brand name 'MPROMODA'."}}
        - Input: "OPENPAY ANGELDELCIE" -> Output: {{"cleaned_name": "OPENPAY", "reasoning": "Extracted payment processor 'OPENPAY'."}}
        - Input: "PLAZA MAYOR" -> Output: {{"cleaned_name": "PLAZA MAYOR", "reasoning": "Identified as a business name."}}
        - Input: "FOTOSDERUNNERGDL" -> Output: {{"cleaned_name": "FOTOSDERUNNERGDL", "reasoning": "Treated as a single business name."}}
        - Input: "LITTLE 8 DE JULIO" -> Output: {{"cleaned_name": "LITTLE", "reasoning": "Extracted brand 'LITTLE' and ignored location '8 DE JULIO'."}}

        Provide the output in a strict JSON format with two keys: "cleaned_name" and "reasoning".
        """
        try:
            response = self.gemini_model.generate_content(prompt)
            cleaned_response = response.text.strip().replace("```json", "").replace("```", "").strip()
            return json.loads(cleaned_response)
        except Exception as e:
            print(f"Error during Gemini call for '{raw_name}': {e}")
            return None

    def search_web(self, query: str, num_results: int = 5) -> Optional[List[Dict[str, str]]]:
        """Performs a web search using the Google Custom Search API."""
        if not self.search_service or not self.api_config.search_cse_id:
            return None

        try:
            res = self.search_service.cse().list(
                q=query, cx=self.api_config.search_cse_id, num=num_results
            ).execute()
            items = res.get('items', [])
            return [{"title": item.get('title'), "link": item.get('link'), "snippet": item.get('snippet')} for item in items]
        except HttpError as e:
            print(f"Error during Google Search for '{query}': {e}")
            return None

    def find_place(self, query: str) -> Optional[Dict[str, Any]]:
        """Performs a Text Search using the Google Places API."""
        if not self.api_config.places_api_key:
            return None

        base_url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
        params = {"query": query, "key": self.api_config.places_api_key, "fields": "name,website,formatted_address"}
        try:
            response = requests.get(base_url, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error during Google Places API call for '{query}': {e}")
            return None

    def validate_and_enrich_from_search(self, search_results: List[Dict], cleaned_name: str) -> Optional[Dict[str, Any]]:
        """
        Uses a second AI pass to extract structured data from search results.
        This method does NOT make final decisions but extracts information for Python-based business logic.
        """
        if not self.gemini_model:
            raise ConnectionError("Gemini model is not configured.")

        formatted_results = ""
        for i, result in enumerate(search_results, 1):
            formatted_results += f"{i}. Title: {result.get('title', 'N/A')}\\n   Link: {result.get('link', 'N/A')}\\n   Snippet: {result.get('snippet', 'N/A')}\\n"

        prompt = f"""
        Analyze the following search results for a business named "{cleaned_name}". Your task is to extract key information from the MOST LIKELY official result. Do not decide, just extract.

        Search Results:
        {formatted_results}

        Based on the single best search result, extract the following information. If no single result is a clear official source, provide data from the best candidate and set 'is_likely_official' to false.

        Provide the output in a strict JSON format with the following keys:
        - "best_match_title": (String) The title of the single best search result you identified.
        - "found_merchant_name": (String) The business name found in the best search result.
        - "website": (String) The full URL from the result. Prioritize the root domain if possible.
        - "social_media_links": (List of strings) Any social media URLs found in the snippet.
        - "evidence_summary": (String) A brief, neutral summary of the match (e.g., "Result #1 appears to be the official site.").
        - "is_likely_official": (Boolean) True if you are confident this is the official business site, false otherwise.
        - "is_closed": (Boolean) True if the result indicates the business is permanently closed.
        - "is_aggregator": (Boolean) True if the link is to an aggregator site (e.g., Yelp, TripAdvisor, YellowPages).
        - "is_social_media": (Boolean) True if the primary link is a social media page.
        """
        try:
            response = self.gemini_model.generate_content(prompt)
            cleaned_response = response.text.strip().removeprefix("```json").removesuffix("```").strip()
            return json.loads(cleaned_response)
        except Exception as e:
            print(f"Error during AI data extraction for '{cleaned_name}': {e}")
            return None