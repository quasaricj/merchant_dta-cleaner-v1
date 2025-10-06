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

    def validate_and_enrich_from_search(self, search_results: List[Dict], cleaned_name: str, query: str) -> Optional[Dict[str, Any]]:
        """
        Uses a master AI prompt to analyze search results and make a final, rule-based
        decision on how to populate the output columns.
        """
        if not self.gemini_model:
            raise ConnectionError("Gemini model is not configured.")

        formatted_results = ""
        for i, result in enumerate(search_results, 1):
            formatted_results += f"Result {i}:\nTitle: {result.get('title', 'N/A')}\nLink: {result.get('link', 'N/A')}\nSnippet: {result.get('snippet', 'N/A')}\n\n"

        prompt = f"""
        You are an expert data analyst for a credit card company. Your task is to clean and enrich merchant data based on the Google Search results provided. You must act as an intelligent human operator and follow the rules precisely.

        **Context:**
        - The original merchant name was pre-cleaned to: "{cleaned_name}"
        - The search query used was: "{query}"

        **Search Results:**
        ---
        {formatted_results}
        ---

        **Your Task:**
        Analyze the search results to find the single best, most official match for the merchant. Then, based on the following strict rules, provide the final values for the output columns in a JSON format.

        **Decision Rules & Column Logic:**

        1.  **`cleaned_merchant_name`**:
            -   The official business name, properly capitalized (e.g., "Reliance Retail").
            -   If it's a franchise like "KFC New Delhi", use only the main brand: "KFC".
            -   If no valid business is found, this MUST be an empty string "".

        2.  **`website`**:
            -   The official, working, and clickable business URL.
            -   **You must explicitly state in the `evidence` that you have mentally "checked" the link to ensure it's not parked, for sale, or under maintenance.**
            -   If no valid website is found, this MUST be an empty string "".

        3.  **`social_media_links`**:
            -   If a `website` is found, this MUST be an empty list `[]`.
            -   If no `website` is found, provide a list of valid, official social media URLs.
            -   If neither website nor socials are found, this MUST be an empty list `[]`.

        **Edge Case Rules (Apply these to make your decision):**

        *   **Multiple Businesses Found**: Pick the closest match based on the query context. State in the `evidence` that other similar businesses were found but you chose the best fit.
        *   **Permanently Closed**: If a business is listed as "permanently closed", it is NOT a valid match. Do not populate any fields.
        *   **Aggregator Sites (Yelp, Uber Eats, etc.)**: A match on an aggregator site IS considered valid evidence *if* no official site is found. Set `website` to "" and populate `social_media_links` if available on the aggregator page.
        *   **Website is a Subpage/Redirect**: A subpage of a larger site (e.g., a mall directory) is NOT a valid website. A redirect to a parent company is acceptable ONLY if it's the official corporate parent. Note this in the `evidence`.
        *   **Social Media as Website**: A social media page is NEVER a valid `website`.

        **Final JSON Output Structure:**
        You must return a single JSON object with the following keys. Do not deviate from this structure.

        ```json
        {{
          "cleaned_merchant_name": "...",
          "website": "...",
          "social_media_links": ["...", "..."],
          "evidence": "A detailed, step-by-step explanation of your reasoning. Start by stating which search result you used as the primary source. Explain why you chose it and why the data is valid according to the rules. If you rejected a match, explain which rule was violated."
        }}
        ```

        **Example of Good Evidence:**
        "Based on Result #2 (Promoda Website), I confirmed the official name is 'Promoda'. I have verified the website link 'https://promoda.com.mx/' is a live and official e-commerce site. The original query included 'TOLUCA', and while the site is national, it represents the correct brand. Therefore, this is a confident match."

        Now, analyze the provided search results and return the final JSON output.
        """
        try:
            # The API call now sends the comprehensive prompt
            response = self.gemini_model.generate_content(prompt)
            # Clean the response to ensure it's valid JSON
            cleaned_response = response.text.strip().replace("```json", "").replace("```", "").strip()
            return json.loads(cleaned_response)
        except Exception as e:
            print(f"Error during AI validation for '{cleaned_name}': {e}")
            return None