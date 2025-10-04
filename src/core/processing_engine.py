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
            if not record.evidence:
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
        """Performs a web search and uses AI to validate the results."""
        search_results = self.api_client.search_web(query)
        record.cost_per_row += cost_estimator.API_COSTS["google_search_per_query"]
        if not search_results:
            return False

        # Use the new AI validation method
        validated_data = self.api_client.validate_and_enrich_from_search(search_results, record.cleaned_merchant_name)
        if self.settings.model_name:
             record.cost_per_row += cost_estimator.CostEstimator.get_model_cost(self.settings.model_name)

        if validated_data and validated_data.get("official_website"):
            record.website = validated_data["official_website"]
            record.socials = validated_data.get("social_media_links", [])
            record.evidence = validated_data.get("evidence", f"Found via Google Search with query: '{query}'.")
            # Ensure evidence_links is populated correctly
            record.evidence_links = [link for link in [record.website] + record.socials if link]
            return True
        elif validated_data:
             # AI decided there was no good match, respect that decision.
             record.evidence = validated_data.get("evidence", "AI analyzed search results and found no definitive official website.")

        return False

    def _build_search_queries(self, record: MerchantRecord) -> List[str]:
        """Constructs a list of search queries based on FR16, ignoring empty fields."""
        name = record.cleaned_merchant_name
        # Ensure optional fields are strings, but handle None or empty strings gracefully
        addr = record.original_address or ""
        city = record.original_city or ""
        country = record.original_country or ""

        # Build query parts
        parts = {
            'name': name,
            'addr': addr,
            'city': city,
            'country': country
        }

        # Define query structures from FR16
        query_structures = [
            ['name', 'addr', 'city', 'country'], # a
            ['name', 'city', 'country'],         # b
            ['name', 'city'],                    # c
            ['name', 'country'],                 # d
            ['name'],                            # e
            ['name', 'addr'],                    # f
        ]

        queries = []
        for structure in query_structures:
            # Join parts only if the corresponding value is not empty
            query_list = [parts[p] for p in structure if parts[p].strip()]
            if query_list:
                queries.append(" ".join(query_list))

        # Remove duplicate queries that might result from empty fields
        return list(dict.fromkeys(queries))

    def _is_valid_place_result(self, result: Optional[Dict]) -> bool:
        """Checks if a Places API result is considered a valid match."""
        return bool(result and result.get("status") == "OK" and result.get("results"))

    def _generate_logo_filename(self, cleaned_name: str) -> str:
        """Creates a standardized logo filename."""
        if not cleaned_name:
            return ""
        safe_name = "".join(c for c in cleaned_name if c.isalnum() or c in " _-").rstrip()
        return f"{safe_name.replace(' ', '_').lower()}_logo.png"