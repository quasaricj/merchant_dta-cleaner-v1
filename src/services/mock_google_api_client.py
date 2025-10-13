# pylint: disable=no-member,broad-except-clause,unused-argument,too-many-instance-attributes
"""
This module provides a MOCK client class for simulating interactions with Google APIs.
It is designed for testing purposes, allowing for the simulation of rate limiting,
quota exhaustion, and other API error conditions without making real network calls.
"""
import time
import json
from typing import Optional, List, Dict, Any
from collections import deque
from src.services.api_util import retry_with_backoff
from src.services.custom_exceptions import (
    MockHttpError429, MockHttpError503, MockQuotaExceededError
)


class MockGoogleApiClient:
    """
    A mock client to simulate interactions with Google APIs for testing.
    It simulates rate limits and returns predictable, hardcoded data.
    """
    GEMINI_RPM_LIMIT = 5  # Requests per minute
    GEMINI_WINDOW_SECONDS = 60 / GEMINI_RPM_LIMIT  # 12 seconds per request
    SEARCH_DAILY_LIMIT = 100

    def __init__(self, api_config: Any, model_name: Optional[str] = None):
        self.api_config = api_config
        self.model_name = model_name
        self.search_call_count = 0
        self.gemini_call_timestamps = deque()
        self.force_service_unavailable = False # Test flag for 503 errors
        self.force_invalid_key = False # Test flag for key validation

    def _api_request_handler(self, api_type: str):
        """
        Central handler to simulate rate limiting and errors before any mock API call.
        """
        if self.force_service_unavailable:
            raise MockHttpError503()

        if api_type == "gemini":
            current_time = time.time()
            # Remove timestamps older than the window
            while self.gemini_call_timestamps and self.gemini_call_timestamps[0] <= current_time - self.GEMINI_WINDOW_SECONDS * 5: # check last 1 minute
                 self.gemini_call_timestamps.popleft()

            if len(self.gemini_call_timestamps) >= self.GEMINI_RPM_LIMIT:
                raise MockHttpError429("Gemini API rate limit exceeded.")
            self.gemini_call_timestamps.append(current_time)

        elif api_type == "search":
            if self.search_call_count >= self.SEARCH_DAILY_LIMIT:
                raise MockQuotaExceededError("Google Search daily quota of 100 queries exceeded.")
            self.search_call_count += 1

    def validate_and_list_models(self, api_key: str) -> Optional[List[str]]:
        """Mocks API key validation."""
        if self.force_invalid_key or not api_key:
            return None
        return ["models/gemini-1.5-flash-latest"]

    def _configure_clients(self, model_name: Optional[str]):
        """Mock configuration. Does nothing as no real clients are needed."""
        pass

    def validate_api_keys(self) -> bool:
        """Mocks the API key validation."""
        if self.force_invalid_key:
            raise ConnectionError("Mock API key validation failed.")
        return True

    @retry_with_backoff()
    def remove_aggregators(self, raw_name: str, return_prompt: bool = False) -> Dict[str, Any]:
        """Mocks the aggregator removal AI call."""
        self._api_request_handler("gemini")
        prompt = "mock aggregator prompt"
        # Return a predictable, cleaned-up response
        if "PAYPAL *" in raw_name:
            result = {"cleaned_name": raw_name.replace("PAYPAL *", "").strip(), "removal_reason": "Removed 'PAYPAL *' prefix."}
        else:
            result = {"cleaned_name": raw_name, "removal_reason": "No aggregator found."}
        return (result, prompt) if return_prompt else result

    @retry_with_backoff()
    def search_web(self, query: str, num_results: int = 5) -> Optional[List[Dict[str, str]]]:
        """Mocks the web search API call."""
        self._api_request_handler("search")
        # Return a generic, useful search result for testing
        return [{
            "title": f"Official Site for {query}",
            "link": f"https://www.example.com/{query.replace(' ', '-').lower()}",
            "snippet": f"The official website for all your {query} needs. Contact us today!"
        }]

    @retry_with_backoff()
    def analyze_search_results(self, search_results: List[Dict], original_name: str, query: str, return_prompt: bool = False) -> Optional[Dict[str, Any]]:
        """Mocks the AI analysis of search results."""
        self._api_request_handler("gemini")
        prompt = "mock analysis prompt"
        # --- Special case for stress testing row-level failure ---
        if "FORCE_FAIL_MERCHANT" in original_name:
            raise MockQuotaExceededError("This is a forced, non-retriable error for testing.")

        # Return a predictable analysis based on mock search results
        result = {
          "cleaned_merchant_name": original_name.title(),
          "website_candidate": next((res['link'] for res in search_results if 'example.com' in res['link']), ""),
          "social_media_candidate": "https://facebook.com/example",
          "business_status": "Operational",
          "supporting_evidence": "Found official site in search results."
        }
        return (result, prompt) if return_prompt else result

    @retry_with_backoff()
    def verify_website_with_ai(self, website_content: str, merchant_name: str, return_prompt: bool = False) -> Optional[Dict[str, Any]]:
        """Mocks the AI verification of website content."""
        self._api_request_handler("gemini")
        prompt = "mock verification prompt"
        # Return a successful verification by default
        result = {
          "is_valid": True,
          "reasoning": "The website appears to be a legitimate and operational business page."
        }
        return (result, prompt) if return_prompt else result

    # --- Utility methods for testing ---
    def reset_counters(self):
        """Resets all counters and flags to their initial state."""
        self.search_call_count = 0
        self.gemini_call_timestamps.clear()
        self.force_service_unavailable = False
        self.force_invalid_key = False