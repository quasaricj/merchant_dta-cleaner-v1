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
        Uses a master AI prompt to analyze search results and extract potential entity information
        based on a detailed set of business rules.
        """
        if not self.gemini_model:
            raise ConnectionError("Gemini model is not configured.")

        formatted_results = ""
        for i, result in enumerate(search_results, 1):
            formatted_results += f"Result {i}:\\nTitle: {result.get('title', 'N/A')}\\nLink: {result.get('link', 'N/A')}\\nSnippet: {result.get('snippet', 'N/A')}\\n\\n"

        prompt = f"""
        You are an expert data analyst for a data cleaning agency. Your task is to solve a critical problem for credit card companies: messy, inconsistent merchant names on transaction records. You must act as an intelligent human researcher to find the true, official merchant information based on the provided search results.

        **THE CORE PROBLEM:**
        Merchant names on credit card statements are often messy. This is because the name is sent by the merchant's bank and can be a legal name, an abbreviation, or include extra details like store numbers or payment aggregator prefixes (e.g., "PAYPAL*", "STRIPE*"). Your job is to cut through this noise and find the ground truth.

        **YOUR TASK:**
        Based on the provided inputs, analyze the search results and return a structured JSON object with the final, correct data. You must follow the rules precisely. Do not invent information. If something isn't found, leave the corresponding value as an empty string or list.

        **INPUTS FOR YOUR ANALYSIS:**
        1.  **Raw Merchant String:** `{raw_name}` (This is the original, messy data)
        2.  **Pre-Cleaned Name (for searching):** `{cleaned_name}`
        3.  **Search Query Used:** `{query}`
        4.  **Search Results:**
            ---
            {formatted_results}
            ---

        **BUSINESS RULES FOR POPULATING THE OUTPUT (MUST BE FOLLOWED EXACTLY):**

        **1. `cleaned_merchant_name`**:
            - The official business name, properly capitalized (e.g., "Reliance Retail", not "RELIANCE RETAIL").
            - If it's a franchise like "KFC New Delhi", use only the main brand name "KFC".
            - If no valid business is found, this MUST be an empty string `""`.

        **2. `website`**:
            - The official, working, and clickable business URL.
            - It must NOT be a parked domain, "for sale" page, or lead to an error.
            - It must NOT be a social media page (e.g., facebook.com).
            - If multiple websites are found, pick the most likely official one.
            - If a site redirects to a parent company, note this in the evidence but still provide the URL if it's the most official link available.
            - If no valid website is found, this MUST be an empty string `""`.

        **3. `social_media_links`**:
            - This field is ONLY populated if a `website` is NOT found.
            - Provide a list of valid, official social media profile URLs (e.g., Facebook, Instagram).
            - If multiple profiles are found, pick the one that best matches the location and branding.
            - A profile must contain business and address information to be considered valid. Do not accept personal profiles.
            - If no valid social media is found (or if a website was found), this MUST be an empty list `[]`.

        **4. `business_status`**:
            - Set to one of the following: "Operational", "Permanently Closed", "Historical/Archived", "Uncertain".
            - You MUST NOT accept businesses that are "Permanently Closed" or "Historical/Archived".

        **5. `match_type`**:
            - Set to one of the following: "Exact Match", "Partial Match", "Aggregator Site", "No Match".
            - "Exact Match": High confidence in a direct match with an official website or verified social page.
            - "Partial Match": A plausible match was found, but it might be from a different location or have a slightly different name.
            - "Aggregator Site": The only strong evidence comes from sites like Yelp, TripAdvisor, etc.
            - "No Match": Could not find any relevant business.

        **6. `evidence`**:
            - **Write in simple, non-technical English.** Explain your reasoning as if to a non-technical auditor.
            - State which search result you used as the primary source and why.
            - Explain how you validated the information based on the rules. For example, if you reject a match, clearly state which rule was violated (e.g., "Rejected because the business is marked as permanently closed in Result 2," or "Rejected website from Result 3 because it is a subpage of a mall directory.").
            - If you find multiple businesses, explain why you chose one over the others.

        **FINAL JSON OUTPUT STRUCTURE (Strict):**
        You must return a single JSON object with the following keys. Do not deviate from this structure.

        ```json
        {{
          "cleaned_merchant_name": "...",
          "website": "...",
          "social_media_links": ["..."],
          "business_status": "...",
          "match_type": "...",
          "evidence": "..."
        }}
        ```

        Now, analyze the inputs and return the final JSON output based on all the rules provided.
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