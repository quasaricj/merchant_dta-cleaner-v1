# pylint: disable=too-few-public-methods,too-many-arguments
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
        self._pre_process_name(record)
        queries = self._build_search_queries(record)
        match_found = False
        for query in queries:
            # The 'Enhanced' mode with Places API is now deprecated in favor of a single, robust search flow.
            # All logic is consolidated into the basic search which now uses the master prompt.
            match_found = self._perform_basic_search(record, query)

            if match_found:
                break

        self._finalize_record(record, match_found)
        return record

    def _pre_process_name(self, record: MerchantRecord):
        """
        Performs light, deterministic cleaning on the raw merchant name.
        """
        import re
        raw_name = record.original_name
        if not raw_name or not isinstance(raw_name, str):
            record.cleaned_merchant_name = ""
            return

        # Remove common machine-generated prefixes
        cleaned_name = re.sub(r'^\d+\s*|^\*\s*|^@\s*', '', raw_name.upper().strip())
        record.cleaned_merchant_name = cleaned_name

    def _perform_basic_search(self, record: MerchantRecord, query: str) -> bool:
        """
        Performs a web search and passes the results to the AI decision engine.
        """
        search_results = self.api_client.search_web(query)
        record.cost_per_row += cost_estimator.API_COSTS["google_search_per_query"]
        if not search_results:
            return False # No search results, move to next query

        # The AI now makes the final decision based on the master prompt.
        ai_decision = self.api_client.validate_and_enrich_from_search(
            search_results, record.cleaned_merchant_name, query
        )
        if self.settings.model_name:
            record.cost_per_row += cost_estimator.CostEstimator.get_model_cost(self.settings.model_name)

        if not ai_decision or not ai_decision.get("cleaned_merchant_name"):
            # AI decided there was no valid match based on the rules.
            record.evidence = ai_decision.get("evidence", "AI rejected the match based on the provided rules.")
            return False

        # If we get here, the AI found a valid match. Populate the record.
        record.cleaned_merchant_name = ai_decision.get("cleaned_merchant_name")
        record.website = ai_decision.get("website")
        record.socials = ai_decision.get("social_media_links", [])
        record.evidence = ai_decision.get("evidence")
        record.evidence_links.append(f"https://www.google.com/search?q={query.replace(' ', '+')}")

        return True # A valid match was found and processed.

    def _finalize_record(self, record: MerchantRecord, match_found: bool):
        """Sets final column values like remarks and logo filename based on strict rules."""
        if match_found:
            record.logo_filename = self._generate_logo_filename(record)
            # Per rules, if a website is not found (even if socials are), remark is "website unavailable".
            record.remarks = "website unavailable" if not record.website else ""
        else:
            # If no match was ever found by the AI, set remark to "NA".
            if not record.evidence:
                record.evidence = f"No valid business match found for '{record.cleaned_merchant_name}' after all search attempts."
            # Per business rules, if no valid match is found, the name must be blank.
            record.cleaned_merchant_name = ""
            record.remarks = "NA"

    def _generate_logo_filename(self, record: MerchantRecord) -> str:
        """Creates a standardized logo filename based on strict rules."""
        if record.website:
            try:
                domain = urlparse(record.website).netloc.replace("www.", "")
                return f"{domain.split('.')[0]}.png"
            except Exception:
                return ""
        if record.socials:
            # Rule: if only socials found, use merchant name without spaces.
            # e.g., "Reliance Retail" -> "RelianceRetail.png"
            safe_name = "".join(record.cleaned_merchant_name.split())
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