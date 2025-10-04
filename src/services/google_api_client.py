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
        """Uses Gemini AI to clean and standardize a merchant name."""
        if not self.gemini_model:
            raise ConnectionError("Gemini model is not configured. Check API key and model selection.")

        prompt = f"""
        Analyze the following raw merchant transaction string: "{raw_name}"
        Your task is to extract the official, clean, and recognizable business name.
        - If it's a franchise, return the main brand name (e.g., "McDonald's").
        - If it includes a location, remove it (e.g., "Starbucks 5th Ave" -> "Starbucks").
        - If it's a generic descriptor, identify it as such (e.g., "Parking Garage").

        Provide the output in a JSON format with two keys:
        1. "cleaned_name": The official business name.
        2. "reasoning": A brief explanation of how you arrived at the name.
        """
        try:
            response = self.gemini_model.generate_content(prompt)
            cleaned_response = response.text.strip().removeprefix("```json").removesuffix("```")
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
        Uses a second AI pass to validate search results and extract the official website and socials.
        This acts as a critical validation layer.
        """
        if not self.gemini_model:
            raise ConnectionError("Gemini model is not configured.")

        # Create a numbered list of search results for the prompt
        formatted_results = ""
        for i, result in enumerate(search_results, 1):
            formatted_results += f"{i}. Title: {result.get('title', 'N/A')}\\n   Link: {result.get('link', 'N/A')}\\n   Snippet: {result.get('snippet', 'N/A')}\\n"

        prompt = f"""
        As a data analyst, your task is to identify the official online presence for the business named "{cleaned_name}" from the following Google Search results.

        Search Results:
        {formatted_results}

        Your instructions are:
        1.  **Find the Official Website:** Scrutinize the links and titles to find the single, most authoritative official website for the business.
            - The best link is the root domain (e.g., 'https://www.starbucks.com').
            - AVOID secondary links like '/careers', '/blog', specific product pages, or news articles.
            - AVOID links to third-party aggregators (like Yelp, DoorDash) or social media pages in this field.
        2.  **Find Social Media Links:** From the official website's snippet or other results, identify direct links to the business's social media profiles (e.g., Facebook, Twitter, Instagram).
        3.  **Handle No Match:** If, after careful analysis, you determine that NONE of the results are the official website for "{cleaned_name}", you MUST return empty strings for all fields.

        Provide the output in a strict JSON format with the following keys:
        - "official_website": The single, official root URL, or "" if not found.
        - "social_media_links": A list of direct social media URLs, or an empty list [] if none are found.
        - "evidence": A brief, one-sentence explanation of your decision. State which search result you chose and why, or explain why no suitable result was found.
        """
        try:
            response = self.gemini_model.generate_content(prompt)
            # Clean the response to ensure it's valid JSON
            cleaned_response = response.text.strip().removeprefix("```json").removesuffix("```").strip()
            return json.loads(cleaned_response)
        except Exception as e:
            print(f"Error during AI validation for '{cleaned_name}': {e}")
            return None