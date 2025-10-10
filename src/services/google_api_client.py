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
from src.services.api_util import retry_with_backoff


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
                # So that validate_api_keys can catch it
                self.gemini_model = None

        if self.api_config.search_api_key:
            try:
                self.search_service = build("customsearch", "v1", developerKey=self.api_config.search_api_key)
            except HttpError as e:
                print(f"Error configuring Search API: {e}")
                # So that validate_api_keys can catch it
                self.search_service = None

    def validate_api_keys(self) -> bool:
        """
        Performs lightweight checks to validate that the configured API keys are working.
        Raises ConnectionError on failure.
        """
        if self.gemini_model:
            try:
                # A simple, low-cost way to check the Gemini key
                self.gemini_model.count_tokens("test")
            except Exception as e:
                raise ConnectionError(f"Gemini API key appears to be invalid or expired. Error: {e}")

        if self.search_service:
            try:
                # A simple, no-cost way to check the Search key setup
                self.search_service.cse().list(q="test", cx=self.api_config.search_cse_id, num=1).execute()
            except HttpError as e:
                # Specifically check for 400/403 which often indicate key/config issues
                if e.resp.status in [400, 403]:
                     raise ConnectionError(f"Google Search API key or CSE ID appears to be invalid. Error: {e}")
                raise # Re-raise other HTTP errors
            except Exception as e:
                raise ConnectionError(f"An unexpected error occurred while validating the Google Search API. Error: {e}")
        return True


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

    @retry_with_backoff()
    def remove_aggregators(self, raw_name: str) -> Dict[str, Any]:
        """
        Uses a targeted AI prompt to identify and remove payment aggregator prefixes
        from a raw merchant string.
        """
        if not self.gemini_model:
            raise ConnectionError("Gemini model is not configured.")
        if not raw_name or not isinstance(raw_name, str) or not raw_name.strip():
            return {"cleaned_name": "", "reasoning": "Input was empty."}

        prompt = f"""
        You are a data cleaning specialist. Your task is to remove common payment aggregator prefixes from a given merchant string.
        Aggregators include, but are not limited to: "PAYPAL *", "PP*", "STRIPE*", "SQ*", "AMZNMKTPLACE", "RAZORPAY*", "PHONEPE*", "UBER EATS*", "GOOGLEPAY*".
        The aggregator can appear anywhere. Your goal is to return only the actual merchant's name.

        - If an aggregator is found, return the cleaned name and explain the removal.
        - If no aggregator is found, return the original name.
        - Preserve the original case of the non-aggregator part of the string.

        **EXAMPLES:**
        - Input: "PAYPAL *MYCOOLSTORE" -> Output: {{"cleaned_name": "MYCOOLSTORE", "removal_reason": "Removed 'PAYPAL *' prefix."}}
        - Input: "SQ*The Coffee Shop" -> Output: {{"cleaned_name": "The Coffee Shop", "removal_reason": "Removed 'SQ*' prefix."}}
        - Input: "Regular Business Name" -> Output: {{"cleaned_name": "Regular Business Name", "removal_reason": "No aggregator found."}}
        - Input: "UBER EATS*Tasty Burger" -> Output: {{"cleaned_name": "Tasty Burger", "removal_reason": "Removed 'UBER EATS*' prefix."}}
        - Input: "AMZNMKTPLACE My Product" -> Output: {{"cleaned_name": "My Product", "removal_reason": "Removed 'AMZNMKTPLACE' prefix."}}

        **TASK:**
        Process the following merchant string: "{raw_name}"

        **OUTPUT (Strict JSON format):**
        Return a single JSON object with two keys: "cleaned_name" and "removal_reason".
        """
        try:
            response = self.gemini_model.generate_content(prompt)
            cleaned_response = response.text.strip().replace("```json", "").replace("```", "").strip()
            return json.loads(cleaned_response)
        except Exception as e:
            print(f"Error during aggregator removal for '{raw_name}': {e}")
            # Fallback to returning the original name if AI fails
            return {"cleaned_name": raw_name, "removal_reason": f"AI processing failed: {e}"}

    @retry_with_backoff()
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

    @retry_with_backoff()
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

    @retry_with_backoff()
    def analyze_search_results(self, search_results: List[Dict], original_name: str, query: str) -> Optional[Dict[str, Any]]:
        """
        Uses an AI prompt to analyze search results and extract candidate information.
        This prompt is for extraction, not final decision-making.
        """
        if not self.gemini_model:
            raise ConnectionError("Gemini model is not configured.")

        formatted_results = ""
        for i, result in enumerate(search_results, 1):
            formatted_results += f"Result {i}:\\nTitle: {result.get('title', 'N/A')}\\nLink: {result.get('link', 'N/A')}\\nSnippet: {result.get('snippet', 'N/A')}\\n\\n"

        prompt = f"""
        You are a data extraction specialist. Your task is to analyze a list of web search results and extract potential business information based on a query. Do not make final decisions; your job is to identify all plausible candidates for a human reviewer (or a downstream process) to evaluate.

        **CONTEXT:**
        - The original, messy merchant name was: "{original_name}"
        - The search query used was: "{query}"
        - The search results are provided below.

        **SEARCH RESULTS:**
        ---
        {formatted_results}
        ---

        **EXTRACTION RULES:**
        1.  **`cleaned_merchant_name`**: Extract the most likely official business name. Capitalize it properly (e.g., "Clean Juice"). If it's a franchise (e.g., "KFC New Delhi"), extract the main brand ("KFC"). If multiple names are plausible, choose the one that appears most frequently or officially in the results.
        2.  **`website_candidates`**: Extract ALL potential official website URLs.
            - A website URL is NOT a social media page (facebook.com, instagram.com).
            - A website URL is NOT a page from an aggregator or directory (yelp.com, tripadvisor.com).
            - List all unique, plausible URLs.
        3.  **`social_media_candidates`**: Extract ALL potential official social media profile URLs (Facebook, Instagram, LinkedIn, etc.).
            - A profile must look like a business page, not a personal one.
            - List all unique, plausible URLs.
        4.  **`business_status`**: Based on the snippets, determine the most likely status: "Operational", "Permanently Closed", "Uncertain".
        5.  **`extraction_summary`**: Briefly explain your findings. For example: "Found a likely business name and two potential websites. One social media link was also identified from the search results." Do not try to make a final conclusion.

        **FINAL JSON OUTPUT STRUCTURE (Strict):**
        Return a single JSON object. Do not deviate from this structure. If nothing is found for a field, use an empty string or an empty list.

        ```json
        {{
          "cleaned_merchant_name": "...",
          "website_candidates": ["...", "..."],
          "social_media_candidates": ["...", "..."],
          "business_status": "...",
          "extraction_summary": "..."
        }}
        ```

        Now, analyze the inputs and return the JSON containing the extracted candidate data.
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
            print(f"Error decoding AI JSON response for '{cleaned_name}': {e}\\nResponse was: {response.text}")
            return None
        except Exception as e:
            print(f"An unexpected error occurred during AI analysis for '{cleaned_name}': {e}")
            return None

    @retry_with_backoff()
    def verify_website_with_ai(self, website_content: str, merchant_name: str) -> Optional[Dict[str, Any]]:
        """
        Uses the AI model to analyze the raw text content of a website to determine
        if it's a valid, operational business site.

        Args:
            website_content: The text/HTML content of the website's main page.
            merchant_name: The name of the merchant being investigated, for context.

        Returns:
            A dictionary containing the AI's verdict, e.g.,
            {"is_valid": True, "reasoning": "The website contains clear business information."}
            or None if an error occurs.
        """
        if not self.gemini_model:
            raise ConnectionError("Gemini model is not configured.")

        # Truncate content to avoid exceeding token limits, focusing on the start of the page.
        truncated_content = website_content[:15000]

        prompt = f"""
        You are a website verification specialist. Your job is to determine if a website is a real, operational business site or if it's invalid for business use.
        Invalid sites include those that are parked, for sale, under construction, show error messages (like 404), or have placeholder/template content with no real information.

        **CONTEXT:**
        - I am verifying a merchant named: "{merchant_name}"
        - The following is the raw text/HTML content from their potential website's home page:
        ---
        {truncated_content}
        ---

        **YOUR TASK:**
        Analyze the provided content and determine the website's status.

        **RULES:**
        1.  **Valid Site:** A valid site must show clear signs of being an active, official business page. Look for things like a company logo, "About Us" section, contact details, product/service descriptions, etc.
        2.  **Invalid Site - Parked/For Sale:** Look for explicit phrases like "This domain is for sale," "parked," "buy this domain."
        3.  **Invalid Site - Under Construction:** Look for "coming soon," or similar language.
        4.  **Invalid Site - Error/Empty:** Look for common error messages (e.g., "Not Found," "Forbidden") or a very small amount of content that indicates an empty page.
        5.  **Invalid Site - Template:** Look for placeholder text like "Lorem Ipsum," "Welcome to your new site," or generic template language without specific business details.

        **OUTPUT:**
        Provide your analysis in a strict JSON format with two keys:
        - `is_valid`: A boolean (`true` if it's a valid business site, `false` otherwise).
        - `reasoning`: A brief, one-sentence explanation for your decision in simple English.

        Example Output 1 (Valid):
        ```json
        {{
          "is_valid": true,
          "reasoning": "The website contains specific company information, including services and contact details."
        }}
        ```

        Example Output 2 (Invalid):
        ```json
        {{
          "is_valid": false,
          "reasoning": "The page explicitly states the domain is parked and for sale."
        }}
        ```

        Now, analyze the provided website content and return the JSON output.
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
            print(f"Error decoding AI JSON response for website verification: {e}\\nResponse was: {response.text}")
            return {{"is_valid": False, "reasoning": "AI response was not valid JSON."}}
        except Exception as e:
            print(f"An unexpected error occurred during AI website verification: {e}")
            return {{"is_valid": False, "reasoning": f"An API error occurred: {e}"}}