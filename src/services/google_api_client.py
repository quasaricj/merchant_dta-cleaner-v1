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

        pre_processed_name = re.sub(r'^[0-9\s*@]+', '', raw_name).strip()

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

    def analyze_search_results(self, search_results: List[Dict], raw_name: str, cleaned_name: str, query: str) -> Optional[Dict[str, Any]]:
        """
        Uses a master AI prompt to analyze search results and extract potential entity information.
        This method does NOT enforce final business rules but provides the data for the
        ProcessingEngine to do so.
        """
        if not self.gemini_model:
            raise ConnectionError("Gemini model is not configured.")

        formatted_results = ""
        for i, result in enumerate(search_results, 1):
            formatted_results += f"Result {i}:\nTitle: {result.get('title', 'N/A')}\nLink: {result.get('link', 'N/A')}\nSnippet: {result.get('snippet', 'N/A')}\n\n"

        prompt = f"""
        You are an expert data analyst. Your task is to analyze the provided search results to find the most likely official information for a given merchant.

        **Inputs:**
        1.  **Raw Merchant String:** `{raw_name}`
        2.  **Pre-Cleaned Name (for searching):** `{cleaned_name}`
        3.  **Search Query Used:** `{query}`
        4.  **Search Results:**
            ---
            {formatted_results}
            ---

        **Your Task:**
        Based on the search results, extract the following information. Do not invent information. If something isn't found, leave the corresponding value as an empty string or list.

        **Output Structure (Strict JSON):**
        ```json
        {{
          "cleaned_merchant_name": "The official, capitalized business name. Extract from title or snippet.",
          "website": "The official, full business URL. Must be a valid, working link. No social media links here.",
          "social_media_links": ["List of official social media profile URLs. E.g., Facebook, Twitter, Instagram."],
          "evidence": "A detailed explanation of your reasoning. Mention which search result you used and why you believe it's the correct match. Note any ambiguities, such as multiple locations or similar names. Also check for signs of a business being permanently closed.",
          "status": "One of: 'MATCH_FOUND', 'PARTIAL_MATCH', 'NO_MATCH', 'BUSINESS_CLOSED', 'AGGREGATOR_SITE_ONLY'"
        }}
        ```

        **Analysis Guidelines:**
        - **`cleaned_merchant_name`**: Find the most plausible official business name from the results. Capitalize it correctly (e.g., "Starbucks Coffee Company"). If it's a franchise, use the main brand name (e.g., "KFC" not "KFC Delhi").
        - **`website`**: Extract the official website. Prioritize direct company domains over directory listings. If a link seems plausible, include it.
        - **`social_media_links`**: Extract links to official social media pages ONLY if no official website is found.
        - **`evidence`**: Be specific. "Based on Result 1, the title 'John's Pizza - Official Site' and the URL 'johnspizza.com' strongly indicate a direct match." If you see "permanently closed" in a snippet, mention it.
        - **`status`**:
            - `MATCH_FOUND`: High confidence in a direct match with an official website or verified social page.
            - `PARTIAL_MATCH`: A plausible match was found, but it might be from a less reliable source like Yelp or a different location.
            - `NO_MATCH`: Could not find any relevant business.
            - `BUSINESS_CLOSED`: Found clear evidence the business is permanently closed.
            - `AGGREGATOR_SITE_ONLY`: The only mentions are on sites like Yelp, TripAdvisor, etc.

        Now, analyze the inputs and return the final JSON output.
        """
        try:
            response = self.gemini_model.generate_content(prompt)
            # Handle potential markdown in the response
            cleaned_response = response.text.strip()
            if cleaned_response.startswith("```json"):
                cleaned_response = cleaned_response[7:]
            if cleaned_response.endswith("```"):
                cleaned_response = cleaned_response[:-3]
            cleaned_response = cleaned_response.strip()

            return json.loads(cleaned_response)
        except (json.JSONDecodeError, TypeError) as e:
            print(f"Error decoding AI JSON response for '{cleaned_name}': {e}\nResponse was: {response.text}")
            return None
        except Exception as e:
            print(f"An unexpected error occurred during AI analysis for '{cleaned_name}': {e}")
            return None