# pylint: disable=too-few-public-methods
"""
This module contains the core business logic for cleaning and enriching a single
merchant record. It orchestrates calls to the Google API client based on the
selected processing mode.
"""
from typing import List, Dict, Optional

from src.core.data_model import MerchantRecord, JobSettings
from src.services.google_api_client import GoogleApiClient
from src.core import cost_estimator


class ProcessingEngine:
    """
    Handles the core logic of cleaning and enriching a single merchant record.
    """

    def __init__(self, settings: JobSettings, api_client: GoogleApiClient):
        self.settings = settings
        self.api_client = api_client

    def process_record(self, record: MerchantRecord) -> MerchantRecord:
        """
        Executes the full cleaning and enrichment workflow for a single record.
        """
        self._clean_name_with_ai(record)
        queries = self._build_search_queries(record)
        match_found = False
        for query in queries:
            if self.settings.mode == "Enhanced" and self.api_client.api_config.places_api_key:
                match_found = self._perform_enhanced_search(record, query)
            else:
                match_found = self._perform_basic_search(record, query)
            if match_found:
                break
        if not record.website:
            record.remarks += " | No definitive website found after all search steps."
            record.evidence = "No match found."
        record.logo_filename = self._generate_logo_filename(record.cleaned_merchant_name)
        return record

    def _clean_name_with_ai(self, record: MerchantRecord):
        """Uses AI to clean the merchant name and updates the record."""
        cleaned_info = self.api_client.clean_merchant_name(record.original_name)
        if self.settings.model_name:
            record.cost_per_row += cost_estimator.CostEstimator.get_model_cost(self.settings.model_name)
        if cleaned_info and cleaned_info.get("cleaned_name"):
            record.cleaned_merchant_name = cleaned_info["cleaned_name"]
            record.remarks = f"AI Cleaning: {cleaned_info.get('reasoning', 'N/A')}"
        else:
            record.cleaned_merchant_name = record.original_name.strip()
            record.remarks = "AI cleaning failed; using original name."

    def _perform_enhanced_search(self, record: MerchantRecord, query: str) -> bool:
        """Performs a Places API search with a fallback to web search."""
        place_result = self.api_client.find_place(query)
        record.cost_per_row += cost_estimator.API_COSTS["google_places_find_place"]
        if self._is_valid_place_result(place_result):
            first_result = place_result["results"][0]
            record.website = first_result.get("website", "")
            official_name = first_result.get("name", record.cleaned_merchant_name)
            record.evidence = f"Found via Google Places: '{official_name}' with query: '{query}'"
            record.evidence_links.append(f"https://www.google.com/maps/search/?api=1&query={query.replace(' ', '+')}")
            return True
        return self._perform_basic_search(record, query)

    def _perform_basic_search(self, record: MerchantRecord, query: str) -> bool:
        """Performs a standard web search."""
        search_results = self.api_client.search_web(query)
        record.cost_per_row += cost_estimator.API_COSTS["google_search_per_query"]
        if search_results:
            best_result = self._find_best_match(search_results, record.cleaned_merchant_name)
            if best_result:
                record.website = best_result.get("link", "")
                record.evidence = f"Found via Google Search with query: '{query}'. Title: '{best_result.get('title')}'"
                record.evidence_links.append(best_result.get("link", ""))
                if "facebook.com" in record.website or "twitter.com" in record.website:
                    record.socials.append(record.website)
                return True
        return False

    def _build_search_queries(self, record: MerchantRecord) -> List[str]:
        """Constructs the list of search queries based on FR16."""
        name = record.cleaned_merchant_name
        addr = record.original_address
        city = record.original_city
        country = record.original_country
        queries = [
            f"{name} {addr} {city} {country}",
            f"{name} {city} {country}",
            f"{name} {city}",
            f"{name} {country}",
            name,
            f"{name} {addr}"
        ]
        return [" ".join(q.split()) for q in queries if q and len(q.split()) > 1]

    def _is_valid_place_result(self, result: Optional[Dict]) -> bool:
        """Checks if a Places API result is considered a valid match."""
        return bool(result and result.get("status") == "OK" and result.get("results"))

    def _find_best_match(self, results: List[Dict], cleaned_name: str) -> Optional[Dict]:
        """Finds the best search result based on name matching."""
        for result in results:
            if cleaned_name.lower() in result.get("title", "").lower():
                return result
        return results[0] if results else None

    def _generate_logo_filename(self, cleaned_name: str) -> str:
        """Creates a standardized logo filename."""
        if not cleaned_name:
            return ""
        safe_name = "".join(c for c in cleaned_name if c.isalnum() or c in " _-").rstrip()
        return f"{safe_name.replace(' ', '_').lower()}_logo.png"