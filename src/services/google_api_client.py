# pylint: disable=no-member
"""
This module provides a client class for interacting with all required Google APIs,
including Google Gemini for AI-powered cleaning and Google Custom Search for
web lookups.
"""
import os
import json
from typing import Optional, List, Dict, Any

import google.generativeai as genai
import requests
from googleapiclient.discovery import build  # type: ignore
from googleapiclient.errors import HttpError  # type: ignore

from src.core.data_model import ApiConfig

class GoogleApiClient:
    """A client to manage interactions with Google APIs."""

    def __init__(self, api_config: ApiConfig):
        self.api_config = api_config
        self.gemini_model = None
        self.search_service = None
        self._configure_clients()

    def _configure_clients(self):
        """Initializes the API clients based on the provided keys."""
        # Configure Gemini
        if self.api_config.gemini_api_key:
            try:
                genai.configure(api_key=self.api_config.gemini_api_key)
                self.gemini_model = genai.GenerativeModel('gemini-1.5-flash-latest')
            except ValueError as e:
                print(f"Error configuring Gemini API: {e}")

        # Configure Custom Search
        if self.api_config.search_api_key:
            try:
                self.search_service = build("customsearch", "v1",
                                            developerKey=self.api_config.search_api_key)
            except HttpError as e:
                print(f"Error configuring Search API: {e}")

    def clean_merchant_name(self, raw_name: str) -> Optional[Dict[str, Any]]:
        """
        Uses Gemini AI to clean and standardize a merchant name.
        Returns a dictionary with cleaned name and reasoning.
        """
        if not self.gemini_model:
            return None

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
            # Use removeprefix/suffix for cleaner and more correct stripping
            cleaned_response = response.text.strip()
            if cleaned_response.startswith("```json"):
                cleaned_response = cleaned_response.removeprefix("```json")
            if cleaned_response.endswith("```"):
                cleaned_response = cleaned_response.removesuffix("```")
            return json.loads(cleaned_response)
        except (ValueError, json.JSONDecodeError) as e:
            print(f"Error during Gemini call for '{raw_name}': {e}")
            return None

    def search_web(self, query: str, num_results: int = 5) -> Optional[List[Dict[str, str]]]:
        """
        Performs a web search using the Google Custom Search API.
        Note: A Custom Search Engine ID (cx) is required.
        """
        if not self.search_service:
            return None

        cx_id = os.environ.get("GOOGLE_CX_ID", "000000000000000000000:00000000000") # Dummy ID
        if cx_id.startswith("000"):
            print("Warning: Google Custom Search CX ID is not configured. Search will fail.")

        try:
            res = self.search_service.cse().list(q=query, cx=cx_id, num=num_results).execute()
            items = res.get('items', [])
            return [{
                "title": item.get('title'),
                "link": item.get('link'),
                "snippet": item.get('snippet')
            } for item in items]
        except HttpError as e:
            print(f"Error during Google Search for '{query}': {e}")
            return None

    def find_place(self, query: str) -> Optional[Dict[str, Any]]:
        """
        Performs a Text Search using the Google Places API.
        """
        if not self.api_config.places_api_key:
            return None

        base_url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
        params = {
            "query": query,
            "key": self.api_config.places_api_key,
            "fields": "name,website,formatted_address" # Request specific fields
        }

        try:
            response = requests.get(base_url, params=params, timeout=10)
            response.raise_for_status()  # Raises an HTTPError for bad responses
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error during Google Places API call for '{query}': {e}")
            return None

if __name__ == '__main__':
    from src.core.config_manager import load_api_config

    api_conf = load_api_config()
    if not api_conf or not api_conf.gemini_api_key:
        print("API configuration not found or incomplete. Run main app to configure.")
    else:
        client = GoogleApiClient(api_conf)

        # Test Gemini
        if client.gemini_model:
            print("Testing Gemini Name Cleaning...")
            gemini_result = client.clean_merchant_name("AMZ*Amazon Prime amzn.com/bill WA")
            print(gemini_result)

        # Test Search
        if client.search_service:
            print("\nTesting Web Search...")
            search_res = client.search_web("O'Malley's Tavern")
            print(search_res)

        # Test Places
        if client.api_config.places_api_key:
            print("\nTesting Places API...")
            place_res = client.find_place("Starbucks near Dublin")
            print(place_res)