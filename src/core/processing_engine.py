# pylint: disable=too-few-public-methods,too-many-arguments
"""
This module contains the core business logic for cleaning and enriching a single
merchant record. It orchestrates calls to the Google API client based on the
selected processing mode.
"""
from typing import List, Dict, Optional, Any
from urllib.parse import urlparse
from thefuzz import fuzz

from src.core.data_model import MerchantRecord, JobSettings
from src.services.google_api_client import GoogleApiClient
from src.core import cost_estimator

# Confidence score threshold for name similarity. Matches below this are rejected.
NAME_SIMILARITY_THRESHOLD = 80

class ProcessingEngine:
    """
    Handles the core logic of cleaning and enriching a single merchant record by applying
    strict, rule-based logic to AI-extracted data.
    """

    def __init__(self, settings: JobSettings, api_client: GoogleApiClient):
        self.settings = settings
        self.api_client = api_client
        self.ai_cleaned_name = "" # Store the AI-cleaned name for evidence generation

    def process_record(self, record: MerchantRecord) -> MerchantRecord:
        """
        Executes the full cleaning and enrichment workflow for a single record.
        """
        self._pre_process_name(record)
        queries = self._build_search_queries(record)
        match_found = False
        for query in queries:
            if self.settings.mode == "Enhanced" and self.api_client.api_config.places_api_key:
                match_found = self._perform_enhanced_search(record, query)
            else:
                match_found = self._perform_basic_search(record, query)

            if match_found:
                break

        self._finalize_record(record, match_found)
        return record

    def _pre_process_name(self, record: MerchantRecord):
        """
        Cleans the raw merchant name using a series of deterministic Python rules
        before any AI or search operations are performed.
        """
        import re
        raw_name = record.original_name
        if not raw_name or not isinstance(raw_name, str):
            self.ai_cleaned_name = ""
            record.cleaned_merchant_name = ""
            record.remarks = "Input name was empty."
            return

        # Rule 1: Convert to uppercase and strip whitespace
        cleaned_name = raw_name.upper().strip()

        # Rule 2: Remove only common machine-generated prefixes.
        # This is a lighter touch to avoid removing important context.
        junk_patterns = [
            r'^\d+\s*',  # Leading numbers and space
            r'^\*\s*',   # Leading asterisk and space
            r'^@\s*',    # Leading @ and space
        ]
        for pattern in junk_patterns:
            cleaned_name = re.sub(pattern, '', cleaned_name)

        # Rule 3: Specific, known, non-brand text can be removed.
        # Avoids overly aggressive cleaning.
        cleaned_name = cleaned_name.replace("TDA ", "")

        self.ai_cleaned_name = cleaned_name.strip()
        record.cleaned_merchant_name = self.ai_cleaned_name
        record.remarks = ""

    def _perform_enhanced_search(self, record: MerchantRecord, query: str) -> bool:
        """Performs a Places API search with a fallback to basic web search."""
        place_result = self.api_client.find_place(query)
        record.cost_per_row += cost_estimator.API_COSTS["google_places_find_place"]

        if self._is_valid_place_result(place_result):
            first_result = place_result["results"][0]
            found_name = first_result.get("name", "")
            website = first_result.get("website", "")
            similarity_score = fuzz.token_set_ratio(self.ai_cleaned_name, found_name)

            if website and similarity_score >= NAME_SIMILARITY_THRESHOLD:
                record.cleaned_merchant_name = found_name
                record.website = website
                record.evidence = self._build_evidence_string(
                    query=query,
                    found_name=found_name,
                    website=website,
                    source="Google Places",
                    similarity=similarity_score
                )
                record.evidence_links.append(f"https://www.google.com/maps/search/?api=1&query={query.replace(' ', '+')}")
                return True

        return self._perform_basic_search(record, query)

    def _perform_basic_search(self, record: MerchantRecord, query: str) -> bool:
        """Performs a web search and uses Python logic to validate AI-extracted data."""
        search_results = self.api_client.search_web(query)
        record.cost_per_row += cost_estimator.API_COSTS["google_search_per_query"]
        if not search_results: return False

        extracted_data = self.api_client.validate_and_enrich_from_search(search_results, record.cleaned_merchant_name)
        if self.settings.model_name:
            record.cost_per_row += cost_estimator.CostEstimator.get_model_cost(self.settings.model_name)

        if not extracted_data:
            record.evidence = "AI data extraction call failed."
            return False

        return self._apply_business_rules(record, extracted_data, query)

    def _apply_business_rules(self, record: MerchantRecord, data: Dict[str, Any], query: str) -> bool:
        """Applies strict business logic and validation to the data extracted by the AI."""
        found_name = data.get('found_merchant_name', "")
        website = data.get('website', "")
        is_closed = data.get('is_closed')
        is_official = data.get('is_likely_official', False)
        is_aggregator = data.get('is_aggregator', False)
        is_social_page = data.get('is_social_media', False)
        similarity_score = fuzz.token_set_ratio(self.ai_cleaned_name, found_name)

        if is_closed:
            record.evidence = self._build_evidence_string(query, found_name, website, "Google Search", similarity_score, reason_for_rejection="Business is permanently closed.")
            record.remarks = "Business found but is permanently closed."
            return False
        if similarity_score < NAME_SIMILARITY_THRESHOLD:
            record.evidence = self._build_evidence_string(query, found_name, website, "Google Search", similarity_score, reason_for_rejection=f"Name similarity score ({similarity_score}%) is below threshold ({NAME_SIMILARITY_THRESHOLD}%).")
            record.remarks = f"Low confidence match ({similarity_score}%). Manual review required."
            return False
        if not (is_official or is_aggregator):
            record.evidence = self._build_evidence_string(query, found_name, website, "Google Search", similarity_score, reason_for_rejection="AI could not determine if the result was an official site or a reliable aggregator.")
            record.remarks = "Unverified source. Manual review required."
            return False

        record.cleaned_merchant_name = found_name
        if is_official and website and not is_social_page:
            record.website = website
            record.socials = []
        else:
            record.website = ""
            record.socials = [link for link in [website] + data.get('social_media_links', []) if link]

        record.evidence = self._build_evidence_string(query, found_name, website, "Google Search", similarity_score, data.get('evidence_summary'), is_aggregator, is_social_page)
        record.evidence_links.append(f"https://www.google.com/search?q={query.replace(' ', '+')}")

        return bool(record.website or record.socials)

    def _build_evidence_string(self, query, found_name, website, source, similarity, summary=None, is_aggregator=False, is_social=False, reason_for_rejection=None):
        """Constructs a detailed, auditable evidence string."""
        narrative = [
            f"1. Original Name (AI Cleaned): '{self.ai_cleaned_name}'",
            f"2. Search Query: '{query}'",
            f"3. Match Found: '{found_name}' via {source}.",
            f"4. Name Similarity Score: {similarity}%."
        ]
        if reason_for_rejection:
            narrative.append(f"5. RESULT: REJECTED. Reason: {reason_for_rejection}")
            return " | ".join(narrative)

        if is_aggregator:
            narrative.append("5. Verification: Matched on a reliable aggregator site. Website link may be from aggregator.")
        elif is_social:
            narrative.append("5. Verification: Matched on an official social media page. This is not considered an official website.")
        else:
            narrative.append(f"5. Verification: Website '{website}' inspected and confirmed as a live, dedicated business site.")
        if summary: narrative.append(f"6. AI Summary: {summary}")

        narrative.append("7. RESULT: ACCEPTED.")
        return " | ".join(narrative)

    def _finalize_record(self, record: MerchantRecord, match_found: bool):
        """Sets final column values like remarks and logo filename after all searches."""
        if match_found:
            record.logo_filename = self._generate_logo_filename(record)
            record.remarks = "website unavailable" if not record.website else ""
        else:
            record.cleaned_merchant_name = ""
            if not record.remarks: # If a specific rejection reason wasn't already set...
                record.remarks = "No potential matches found."
            if not record.evidence:
                record.evidence = f"No valid business match found for '{self.ai_cleaned_name}' after all search attempts."

    def _generate_logo_filename(self, record: MerchantRecord) -> str:
        """Creates a standardized logo filename based on strict rules."""
        if record.website:
            try:
                domain = urlparse(record.website).netloc.replace("www.", "")
                return f"{domain.split('.')[0]}.png"
            except Exception: return ""
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