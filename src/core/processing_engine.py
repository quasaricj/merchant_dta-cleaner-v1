# pylint: disable=too-few-public-methods,too-many-arguments,too-many-locals
"""
This module contains the core business logic for cleaning and enriching a single
merchant record. It orchestrates calls to the Google API client based on the
selected processing mode.
"""
from typing import List, Dict, Optional, Any, Callable
from urllib.parse import urlparse
import re

from src.core.data_model import MerchantRecord, JobSettings
from src.services.google_api_client import GoogleApiClient
from src.core import cost_estimator


class ProcessingEngine:
    """
    Handles the core logic of cleaning and enriching a single merchant record by applying
    strict, rule-based logic to AI-extracted data.
    """

    def __init__(self, settings: JobSettings, api_client: GoogleApiClient, view_text_website_func: Callable[[str], str]):
        self.settings = settings
        self.api_client = api_client
        self.view_text_website = view_text_website_func

    def process_record(self, record: MerchantRecord) -> MerchantRecord:
        """
        Executes the full cleaning and enrichment workflow for a single record.
        It implements the 6-step search logic, stopping at the first valid result.
        """
        self._pre_process_name(record)
        queries = self._build_search_queries(record)

        best_analysis = None
        final_query = None
        last_analysis = None
        last_query = None

        for query in queries:
            analysis = self._perform_search_and_analysis(record, query)
            if not analysis:
                continue

            last_analysis = analysis
            last_query = query

            # If a plausible match is found, consider it the best so far and stop.
            if analysis.get("status") in ["MATCH_FOUND", "PARTIAL_MATCH", "AGGREGATOR_SITE_ONLY"]:
                best_analysis = analysis
                final_query = query
                break

        if best_analysis and final_query:
            # A plausible match was found, apply the main business logic.
            self._apply_business_rules(record, best_analysis, final_query)
        elif last_analysis and last_query:
            # No plausible match, but we have some analysis (e.g., BUSINESS_CLOSED).
            # Let the business rules handle this terminal state.
            self._apply_business_rules(record, last_analysis, last_query)
        else:
            # No analysis was ever returned from the API, so this is a hard failure.
            record.cleaned_merchant_name = "" # Ensure name is blank
            record.website = ""
            record.socials = []
            record.logo_filename = ""
            record.remarks = "NA"
            record.evidence = f"No valid business match found for '{record.original_name}' after all search attempts."

        return record

    def _pre_process_name(self, record: MerchantRecord):
        """
        Performs very light, deterministic cleaning on the raw merchant name
        before passing it to the AI.
        """
        raw_name = record.original_name
        if not raw_name or not isinstance(raw_name, str):
            record.cleaned_merchant_name = ""
            return

        # Remove leading numbers, special chars, and known prefixes
        cleaned_name = re.sub(r'^\d+\s*|^\W+', '', raw_name.upper().strip())
        record.cleaned_merchant_name = cleaned_name.strip()

    def _perform_search_and_analysis(self, record: MerchantRecord, query: str) -> Optional[Dict[str, Any]]:
        """
        Performs a web search and returns the AI's analysis object.
        """
        search_results = self.api_client.search_web(query)
        record.cost_per_row += cost_estimator.API_COSTS["google_search_per_query"]
        if not search_results:
            return None

        ai_analysis = self.api_client.analyze_search_results(
            search_results, record.original_name, record.cleaned_merchant_name, query
        )
        if self.settings.model_name:
            record.cost_per_row += cost_estimator.CostEstimator.get_model_cost(self.settings.model_name)

        return ai_analysis

    def _apply_business_rules(self, record: MerchantRecord, analysis: Dict[str, Any], query: str):
        """
        Applies the strict business logic from the SRS to populate the final record fields.
        """
        status = analysis.get("status")

        # Rule: Do not accept "permanently closed" businesses.
        if status == "BUSINESS_CLOSED":
            record.cleaned_merchant_name = ""
            record.remarks = "NA"
            record.evidence = analysis.get("evidence", "Business found but is permanently closed.")
            return

        # Rule: If no valid match, leave fields blank and set remarks to "NA".
        if status == "NO_MATCH":
            record.cleaned_merchant_name = ""
            record.remarks = "NA"
            record.evidence = analysis.get("evidence", "No valid business match found.")
            return

        # A match of some kind was found. Populate fields according to rules.
        record.cleaned_merchant_name = analysis.get("cleaned_merchant_name", "")
        record.evidence = analysis.get("evidence", "")
        record.evidence_links.append(f"https://www.google.com/search?q={query.replace(' ', '+')}")

        website_url = analysis.get("website", "")
        social_links = analysis.get("social_media_links", [])

        # Rule: Website takes precedence. Social links are only used if no website is found.
        if website_url:
            # Here you could add website validation if needed, e.g., using self.view_text_website
            # For now, we trust the AI's analysis from the prompt.
            record.website = website_url
            record.socials = [] # Ensure socials are blank if website exists
            record.remarks = "" # Clear remarks if website is found
        elif social_links:
            record.website = ""
            record.socials = social_links
            record.remarks = "website unavailable"
        else:
            # Found a merchant, but no website or socials
            record.website = ""
            record.socials = []
            record.remarks = "website unavailable"

        # Rule: Set logo filename based on website or merchant name.
        record.logo_filename = self._generate_logo_filename(record)


    def _generate_logo_filename(self, record: MerchantRecord) -> str:
        """Creates a standardized logo filename based on strict rules."""
        # Rule: If website found, use its domain as filename.
        if record.website:
            try:
                url = record.website
                if not url.startswith(('http://', 'https://')):
                    url = 'http://' + url
                domain = urlparse(url).netloc.replace("www.", "")
                # Take the core part of the domain (e.g., 'google' from 'google.co.in')
                return f"{domain.split('.')[0]}.png"
            except Exception:
                return "" # Should not happen with valid URLs

        # Rule: If only socials found, use merchant name.
        if record.socials and record.cleaned_merchant_name:
            safe_name = "".join(re.findall(r'\w+', record.cleaned_merchant_name.lower()))
            return f"{safe_name}.png"

        # Rule: If neither found, leave blank.
        return ""

    def _build_search_queries(self, record: MerchantRecord) -> List[str]:
        """Constructs a list of search queries based on FR16, ignoring empty fields."""
        name = record.cleaned_merchant_name
        # Use original fields for address parts as they are more likely to be complete
        addr = record.original_address or ""
        city = record.original_city or ""
        country = record.original_country or ""

        parts = {'name': name, 'addr': addr, 'city': city, 'country': country}

        # 6-step search logic from SRS
        query_structures = [
            ['name', 'addr', 'city', 'country'], # 1. Merchant + address + city + country
            ['name', 'city', 'country'],        # 2. Merchant + city + country
            ['name', 'city'],                   # 3. Merchant + city
            ['name', 'country'],                # 4. Merchant + country
            ['name'],                           # 5. Merchant only
            ['name', 'addr'],                   # 6. Merchant + street
        ]

        queries = []
        for structure in query_structures:
            # Join parts that are not empty
            query_list = [parts[p] for p in structure if parts.get(p, "").strip()]
            if query_list:
                # Create a single string query, ensuring name is always first
                query_str = " ".join(query_list)
                queries.append(query_str)

        # Return a unique list of queries in the specified order.
        return list(dict.fromkeys(queries))

    def _is_valid_place_result(self, result: Optional[Dict]) -> bool:
        """Checks if a Places API result is considered a valid match."""
        return bool(result and result.get("status") == "OK" and result.get("results"))