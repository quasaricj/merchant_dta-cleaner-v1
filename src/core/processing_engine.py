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
        Executes a dynamic 6-step search, verifying promising results with AI and
        halting as soon as a satisfactory one is confirmed.
        """
        self._pre_process_name(record)
        queries = self._build_search_queries(record)

        final_analysis = None
        final_query = None
        evidence_trail = []

        for i, query in enumerate(queries):
            analysis = self._perform_search_and_analysis(record, query)
            if not analysis:
                evidence_trail.append(f"Query {i+1} ('{query}') yielded no usable analysis.")
                continue

            # Always keep the latest analysis in case we fall through the whole loop
            final_analysis = analysis
            final_query = query
            base_evidence = f"Query {i+1} ('{query}') -> '{analysis.get('match_type')}/{analysis.get('business_status')}'"

            # Check if the result is promising enough to attempt AI website verification.
            is_promising = (analysis.get("match_type") == "Exact Match" and
                            analysis.get("business_status") == "Operational" and
                            bool(analysis.get("website")))

            if is_promising:
                website_url = analysis.get("website", "")
                verification = self._verify_website_url(website_url, record)
                analysis['website_verification'] = verification  # Store verification result

                if verification and verification.get("is_valid"):
                    evidence_trail.append(f"{base_evidence}. Website verified: {verification.get('reasoning')}. Match found, halting search.")
                    final_analysis = analysis  # This is our definitive result
                    break  # Satisfactory result found, stop searching.
                else:
                    reason = verification.get('reasoning', 'Verification failed')
                    evidence_trail.append(f"{base_evidence}. Website rejected: {reason}. Continuing search.")
            else:
                evidence_trail.append(f"{base_evidence}. Not a high-confidence match, continuing search.")

        if final_analysis and final_query:
            self._apply_business_rules(record, final_analysis, final_query, evidence_trail)
        else:
            record.cleaned_merchant_name = ""
            record.website = ""
            record.socials = []
            record.logo_filename = ""
            record.remarks = "NA"
            record.evidence = f"No valid business match found. Search trail: {' -> '.join(evidence_trail)}"

        return record

    def _pre_process_name(self, record: MerchantRecord):
        """Performs light, deterministic cleaning on the raw merchant name."""
        raw_name = record.original_name
        if not raw_name or not isinstance(raw_name, str):
            record.cleaned_merchant_name = ""
            return
        cleaned_name = re.sub(r'^\d+\s*|^\W+', '', raw_name.upper().strip())
        record.cleaned_merchant_name = cleaned_name.strip()

    def _perform_search_and_analysis(self, record: MerchantRecord, query: str) -> Optional[Dict[str, Any]]:
        """Performs a web search and returns the AI's analysis object."""
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

    def _verify_website_url(self, url: str, record: MerchantRecord) -> Optional[Dict[str, Any]]:
        """
        Fetches website content and uses AI to verify if it's a legitimate business site.
        Returns the verification result and handles cost attribution.
        """
        if not url:
            return {"is_valid": False, "reasoning": "No URL provided."}
        try:
            content = self.view_text_website(url)
            if not content or not content.strip():
                return {"is_valid": False, "reasoning": "Website content was empty or could not be fetched."}

            if self.settings.model_name:
                record.cost_per_row += cost_estimator.CostEstimator.get_model_cost(self.settings.model_name)

            return self.api_client.verify_website_with_ai(content, record.cleaned_merchant_name)
        except Exception as e:
            print(f"Error during website verification for {url}: {e}")
            return {"is_valid": False, "reasoning": f"An unexpected error occurred: {e}"}

    def _apply_business_rules(self, record: MerchantRecord, analysis: Dict[str, Any], query: str, evidence_trail: List[str]):
        """
        Applies strict business logic to populate the final record fields based on AI analysis
        and AI-powered website verification.
        """
        website_url = analysis.get("website", "")
        social_links = analysis.get("social_media_links", [])

        # Step 1: Perform final website verification if it wasn't done already
        verification = analysis.get('website_verification')
        if not verification and website_url:
            # This happens if the first promising result was actually the last query tried.
            verification = self._verify_website_url(website_url, record)
            analysis['website_verification'] = verification
            evidence_trail.append(f"Final verification on last resort URL: {verification.get('reasoning', 'N/A')}")

        # Step 2: Set the final evidence using the new narrative generator
        record.evidence = self._generate_final_evidence(analysis, evidence_trail)

        # Step 3: Apply final business logic based on the outcomes
        business_status = analysis.get("business_status")
        match_type = analysis.get("match_type")
        is_website_valid = verification and verification.get("is_valid")

        # Rejection rules
        if business_status in ["Permanently Closed", "Historical/Archived"] or match_type == "No Match":
            record.cleaned_merchant_name = ""
            record.remarks = "NA"
            return

        # Acceptance rules
        record.cleaned_merchant_name = analysis.get("cleaned_merchant_name", "")
        record.evidence_links.append(f"https://www.google.com/search?q={query.replace(' ', '+')}")

        if is_website_valid:
            record.website = website_url
            record.socials = []
            record.remarks = ""
        elif social_links:
            record.website = ""
            record.socials = social_links
            record.remarks = "website unavailable"
        else:
            record.website = ""
            record.socials = []
            record.remarks = "website unavailable"

        record.logo_filename = self._generate_logo_filename(record)

    def _generate_final_evidence(self, analysis: Dict[str, Any], evidence_trail: List[str]) -> str:
        """
        Constructs a clear, human-readable evidence string based on the final analysis
        and the entire search process.
        """
        match_type = analysis.get("match_type", "N/A")
        business_status = analysis.get("business_status", "N/A")
        ai_evidence = analysis.get("evidence", "AI evidence was not provided.")
        verification = analysis.get("website_verification")
        trail_str = ' -> '.join(evidence_trail)

        # Handle terminal rejection cases first
        if business_status in ["Permanently Closed", "Historical/Archived"]:
            return f"Rejected because the business was found to be '{business_status}'. Search trail: {trail_str}"
        if match_type == "No Match":
            return f"No valid business match was found after all attempts. Search trail: {trail_str}"

        # Build the narrative for a plausible match
        narrative = f"The AI's analysis of search results identified a '{match_type}' for a business with status '{business_status}'. "
        narrative += f"The AI's reasoning was: '{ai_evidence}'. "

        if verification:
            if verification.get("is_valid"):
                narrative += f"A follow-up AI check of the website confirmed it is a valid, operational site. "
                narrative += f"Verification reason: '{verification.get('reasoning', 'N/A')}'. "
            else:
                narrative += f"However, a follow-up AI check of the website REJECTED it. "
                narrative += f"Rejection reason: '{verification.get('reasoning', 'N/A')}'. "
        else:
            narrative += "No website was found or verified. "

        narrative += f"The full search process was: {trail_str}"
        return narrative

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