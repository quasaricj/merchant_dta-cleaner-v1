# pylint: disable=too-few-public-methods
"""
This module contains the core business logic for cleaning and enriching a single
merchant record. It orchestrates calls to the Google API client based on the
selected processing mode.
"""
from typing import List, Dict, Optional, Any
from urllib.parse import urlparse

from src.core.data_model import MerchantRecord, JobSettings
from src.services.google_api_client import GoogleApiClient
from src.core import cost_estimator


class ProcessingEngine:
    """
    Handles the core logic of cleaning and enriching a single merchant record by applying
    strict, rule-based logic to AI-extracted data.
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
                break  # Stop on the first successful match

        self._finalize_record(record, match_found)
        return record

    def _clean_name_with_ai(self, record: MerchantRecord):
        """Uses AI to clean the merchant name and updates the record."""
        cleaned_info = self.api_client.clean_merchant_name(record.original_name)
        if self.settings.model_name:
            record.cost_per_row += cost_estimator.CostEstimator.get_model_cost(self.settings.model_name)

        if cleaned_info and cleaned_info.get("cleaned_name"):
            record.cleaned_merchant_name = cleaned_info["cleaned_name"]
            # Remarks are now handled in _finalize_record
            record.remarks = ""
        else:
            record.cleaned_merchant_name = record.original_name.strip()
            record.remarks = "AI cleaning failed; using original name."

    def _perform_enhanced_search(self, record: MerchantRecord, query: str) -> bool:
        """Performs a Places API search with a fallback to basic web search."""
        place_result = self.api_client.find_place(query)
        record.cost_per_row += cost_estimator.API_COSTS["google_places_find_place"]

        if self._is_valid_place_result(place_result):
            first_result = place_result["results"][0]
            record.cleaned_merchant_name = first_result.get("name", record.cleaned_merchant_name)
            record.website = first_result.get("website", "")
            record.evidence = f"Found via Google Places: '{record.cleaned_merchant_name}'. Query: '{query}'"
            record.evidence_links.append(f"https://www.google.com/maps/search/?api=1&query={query.replace(' ', '+')}")
            return bool(record.website)  # Success if a website is found

        return self._perform_basic_search(record, query)

    def _perform_basic_search(self, record: MerchantRecord, query: str) -> bool:
        """Performs a web search and uses Python logic to validate AI-extracted data."""
        search_results = self.api_client.search_web(query)
        record.cost_per_row += cost_estimator.API_COSTS["google_search_per_query"]
        if not search_results:
            return False

        extracted_data = self.api_client.validate_and_enrich_from_search(search_results, record.cleaned_merchant_name)
        if self.settings.model_name:
            record.cost_per_row += cost_estimator.CostEstimator.get_model_cost(self.settings.model_name)

        if not extracted_data:
            record.evidence = "AI data extraction call failed."
            return False

        return self._apply_business_rules(record, extracted_data, query)

    def _apply_business_rules(self, record: MerchantRecord, data: Dict[str, Any], query: str) -> bool:
        """Applies strict business logic to the data extracted by the AI."""
        if data.get('is_closed'):
            record.evidence = f"Match found ('{data.get('found_merchant_name')}') but is reported as permanently closed. No data populated. Evidence: {data.get('evidence_summary')}"
            return False  # Not a valid match per business rules

        is_official = data.get('is_likely_official', False)
        is_aggregator = data.get('is_aggregator', False)
        if not (is_official or is_aggregator):
            record.evidence = f"Match found ('{data.get('found_merchant_name')}') but was not deemed an official or reliable aggregator site. Evidence: {data.get('evidence_summary')}"
            return False

        record.cleaned_merchant_name = data.get('found_merchant_name', record.cleaned_merchant_name)

        website = data.get('website', "")
        is_social_page = data.get('is_social_media', False)

        if is_official and website and not is_social_page:
            record.website = website
            record.socials = []  # Rule: If website is found, socials must be blank
        else:
            record.website = ""  # Rule: Social media pages or aggregators are not official websites
            record.socials = [link for link in [website] + data.get('social_media_links', []) if link]

        record.evidence = self._build_evidence_string(data, query)
        record.evidence_links.append(f"https://www.google.com/search?q={query.replace(' ', '+')}")

        return bool(record.website or record.socials)

    def _build_evidence_string(self, data: Dict[str, Any], query: str) -> str:
        """Constructs the detailed evidence string based on the match."""
        summary = data.get('evidence_summary', 'No summary provided.')
        evidence = f"Query: '{query}'. Evidence: {summary}"
        if data.get('is_aggregator'):
            evidence += f" Source is an aggregator site ({data.get('website')})."
        elif data.get('is_social_media'):
            evidence += " Source is a social media page, not an official website."
        return evidence

    def _finalize_record(self, record: MerchantRecord, match_found: bool):
        """Sets final column values like remarks and logo filename after all searches."""
        if match_found:
            record.logo_filename = self._generate_logo_filename(record)
            if not record.website:
                record.remarks = "website unavailable"
            else:
                record.remarks = ""  # Clear remarks on success
        else:
            record.cleaned_merchant_name = ""  # Rule: Leave blank if not found
            record.remarks = "NA"
            if not record.evidence:
                record.evidence = "No valid business match found after all search attempts."

    def _generate_logo_filename(self, record: MerchantRecord) -> str:
        """Creates a standardized logo filename based on strict rules."""
        if record.website:
            domain = urlparse(record.website).netloc.replace("www.", "")
            return f"{domain.split('.')[0]}.png"
        if record.socials:
            safe_name = "".join(c for c in record.cleaned_merchant_name if c.isalnum()).lower()
            return f"{safe_name}.png" if safe_name else ""
        return ""

    def _build_search_queries(self, record: MerchantRecord) -> List[str]:
        """Constructs a list of search queries based on FR16, ignoring empty fields."""
        name = record.cleaned_merchant_name
        addr = record.original_address or ""
        city = record.original_city or ""
        country = record.original_country or ""
        parts = {'name': name, 'addr': addr, 'city': city, 'country': country}
        query_structures = [
            ['name', 'addr', 'city', 'country'],
            ['name', 'city', 'country'],
            ['name', 'city'],
            ['name', 'country'],
            ['name'],
            ['name', 'addr'],
        ]
        queries = []
        for structure in query_structures:
            query_list = [parts[p] for p in structure if parts.get(p, "").strip()]
            if query_list:
                queries.append(" ".join(query_list))
        return list(dict.fromkeys(queries))

    def _is_valid_place_result(self, result: Optional[Dict]) -> bool:
        """Checks if a Places API result is considered a valid match."""
        return bool(result and result.get("status") == "OK" and result.get("results"))