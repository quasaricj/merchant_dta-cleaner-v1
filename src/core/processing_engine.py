# pylint: disable=too-few-public-methods,too-many-arguments,too-many-locals
"""
This module contains the core business logic for cleaning and enriching a single
merchant record. It orchestrates calls to the Google API client based on the
selected processing mode and implements the strict, rule-based workflow.
"""
from typing import List, Dict, Optional, Any, Callable
from urllib.parse import urlparse
import re
import requests

from src.core.data_model import MerchantRecord, JobSettings
from src.services.google_api_client import GoogleApiClient
from src.core import cost_estimator


class ProcessingEngine:
    """
    Handles the core logic of cleaning and enriching a single merchant record by applying
    a strict, multi-step, rule-based workflow to find and validate business information.
    """

    def __init__(self, settings: JobSettings, api_client: GoogleApiClient, view_text_website_func: Callable[[str], str]):
        self.settings = settings
        self.api_client = api_client
        self.view_text_website = view_text_website_func

    def _is_merchant_name_in_search_item(self, merchant_name: str, item: Dict[str, str]) -> bool:
        """
        Checks if the merchant name (or a simplified version) is in the search result's
        title or snippet. This is the core of the 'Strict Match Mode'.
        """
        # Normalize both the merchant name and the search content for a more robust comparison.
        # This removes punctuation and converts to lower case.
        normalised_name = re.sub(r'[^\w\s]', '', merchant_name).lower().strip()

        title = item.get('title', '')
        snippet = item.get('snippet', '')

        normalised_content = re.sub(r'[^\w\s]', '', f"{title} {snippet}").lower()

        # Simple substring check. Can be enhanced with tokenization if needed.
        return normalised_name in normalised_content

    def process_record(self, record: MerchantRecord) -> MerchantRecord:
        """
        Executes the strict 6-step search and validation workflow.
        """
        # Step 1: Pre-process name
        aggregator_result = self._remove_aggregators(record)
        aggregator_reason = aggregator_result.get("removal_reason", "No aggregator check performed.")
        cleaned_name_for_search = aggregator_result.get("cleaned_name", record.original_name)

        # Initialize variables
        validated_website = None
        final_analysis = None
        best_social_candidate = None
        all_social_candidates = []
        evidence_trail = [f"Aggregator Check: {aggregator_reason}"]
        if self.settings.strict_match:
            evidence_trail.append("STRICT MATCH MODE ENABLED: Will only consider search results with explicit name match.")

        # Step 2: Build queries
        queries = self._build_search_queries(cleaned_name_for_search, record)

        # Step 3 & 4: The main search-and-verify loop
        for i, query in enumerate(queries):
            evidence_trail.append(f"Query {i+1}: '{query}'")
            search_results = self.api_client.search_web(query)
            record.cost_per_row += cost_estimator.API_COSTS["google_search_per_query"]
            if not search_results:
                evidence_trail.append(" -> No web results found.")
                continue

            # --- Strict Match Logic ---
            if self.settings.strict_match:
                original_results_count = len(search_results)
                search_results = [item for item in search_results if self._is_merchant_name_in_search_item(cleaned_name_for_search, item)]
                evidence_trail.append(f" -> Strict match filtering: {len(search_results)} of {original_results_count} results passed.")
                if not search_results:
                    continue # Skip to the next query if no results pass the strict filter

            # --- AI Analysis (on filtered or all results) ---
            analysis = self.api_client.analyze_search_results(search_results, record.original_name, query)
            if self.settings.model_name:
                record.cost_per_row += cost_estimator.CostEstimator.get_model_cost(self.settings.model_name, "analysis")
            if not analysis:
                evidence_trail.append(" -> AI analysis of results failed.")
                continue

            final_analysis = analysis
            evidence_trail.append(f" -> AI Summary: '{analysis.get('extraction_summary', 'N/A')}'")
            all_social_candidates.extend(analysis.get("social_media_candidates", []))

            # Step 5: Validate website candidates
            website_candidates = analysis.get("website_candidates", [])
            for website_url in website_candidates:
                verification = self._verify_website_url(website_url, record)
                if verification and verification.get("is_valid"):
                    validated_website = website_url
                    evidence_trail.append(f" -> SUCCESS: Website '{website_url}' verified. Reason: {verification.get('reasoning')}. Halting search.")
                    break
                else:
                    reason = verification.get('reasoning', 'Verification failed')
                    evidence_trail.append(f" -> Website '{website_url}' rejected. Reason: {reason}.")

            if validated_website:
                break

        # Step 6 & 7: Apply final business rules and generate evidence
        # Prioritize rejecting closed businesses based on the last available analysis
        if final_analysis and final_analysis.get("business_status") in ["Permanently Closed", "Historical/Archived"]:
            evidence_trail.append(f"Rejected based on final analysis status: {final_analysis.get('business_status')}")
            self._apply_business_rules(record, final_analysis, None, None, evidence_trail, query)
        elif validated_website and final_analysis:
            self._apply_business_rules(record, final_analysis, validated_website, None, evidence_trail, query)
        elif all_social_candidates and final_analysis:
            # No website found, so pick the best social link if available
            best_social_candidate = self._choose_best_social_link(all_social_candidates)
            evidence_trail.append(f"No website validated. Falling back to best social media link: {best_social_candidate}")
            self._apply_business_rules(record, final_analysis, None, best_social_candidate, evidence_trail, queries[-1])
        else:
            # No usable information found at all
            record.cleaned_merchant_name = ""
            record.website = ""
            record.socials = []
            record.logo_filename = ""
            record.remarks = "NA"
            record.evidence = f"No valid business match found after all attempts. Search trail: {' -> '.join(evidence_trail)}"

        return record

    def _remove_aggregators(self, record: MerchantRecord) -> Dict[str, Any]:
        """Calls the API to remove aggregator strings from the merchant name."""
        if not record.original_name or not isinstance(record.original_name, str):
            return {"cleaned_name": "", "removal_reason": "Original name is empty or invalid."}

        aggregator_result = self.api_client.remove_aggregators(record.original_name)
        if self.settings.model_name:
            record.cost_per_row += cost_estimator.CostEstimator.get_model_cost(self.settings.model_name, "utility")
        return aggregator_result

    def _verify_website_url(self, url: str, record: MerchantRecord) -> Optional[Dict[str, Any]]:
        """
        Fetches website content and uses AI to verify if it's a legitimate business site.
        """
        if not url:
            return {"is_valid": False, "reasoning": "No URL provided."}
        try:
            content = self.view_text_website(url)
            if not content or not content.strip():
                return {"is_valid": False, "reasoning": "Website content was empty or could not be fetched."}

            if self.settings.model_name:
                record.cost_per_row += cost_estimator.CostEstimator.get_model_cost(self.settings.model_name, "verification")

            return self.api_client.verify_website_with_ai(content, record.original_name)
        except requests.exceptions.RequestException as e:
            # Catch the specific exception re-raised from tools.py
            reason = f"Website fetch failed: {e}"
            print(f"Error during website verification for {url}: {reason}")
            return {"is_valid": False, "reasoning": reason}
        except Exception as e:
            # Catch any other unexpected errors
            print(f"An unexpected error occurred during website verification for {url}: {e}")
            return {"is_valid": False, "reasoning": f"An unexpected error occurred: {e}"}

    def _apply_business_rules(self, record: MerchantRecord, analysis: Dict[str, Any], validated_website: Optional[str], social_link: Optional[str], evidence_trail: List[str], final_query: str):
        """
        Applies strict business logic based on the final validated outcome.
        """
        business_status = analysis.get("business_status")

        # Rejection rule: Ignore permanently closed or invalid businesses
        if business_status in ["Permanently Closed", "Historical/Archived"]:
            record.cleaned_merchant_name = ""
            record.remarks = "NA"
            record.evidence = self._generate_final_evidence(analysis, validated_website, social_link, evidence_trail, "Rejected due to business status.")
            return

        # Acceptance rules
        record.cleaned_merchant_name = analysis.get("cleaned_merchant_name", "")
        record.evidence_links.append(f"https://www.google.com/search?q={final_query.replace(' ', '+')}")

        if validated_website:
            record.website = validated_website
            record.socials = [] # Rule: Clear socials if website is found
            record.remarks = ""
        elif social_link:
            record.website = ""
            record.socials = [social_link]
            record.remarks = "website unavailable"
        else:
            # This case happens if analysis was positive but website/socials were empty
            record.website = ""
            record.socials = []
            record.remarks = "website unavailable"

        record.evidence = self._generate_final_evidence(analysis, validated_website, social_link, evidence_trail, "Match found and processed.")
        record.logo_filename = self._generate_logo_filename(record)

    def _generate_final_evidence(self, analysis: Dict[str, Any], website: Optional[str], social: Optional[str], trail: List[str], conclusion: str) -> str:
        """
        Constructs a clear, human-readable evidence string from the entire process.
        """
        trail_str = " | ".join(trail)
        summary = analysis.get('extraction_summary', 'No summary provided.')

        narrative = f"Conclusion: {conclusion}\n"
        if website:
            narrative += f"Final Validated Website: {website}\n"
        elif social:
            narrative += f"Final Social Media (no website found): {social}\n"
        else:
            narrative += "No validated website or social media was found.\n"

        narrative += f"AI Extraction Summary: {summary}\n"
        narrative += f"Full Search & Verification Trail: {trail_str}"

        return narrative.strip()

    def _generate_logo_filename(self, record: MerchantRecord) -> str:
        """Creates a standardized logo filename based on strict rules."""
        # Rule: If website found, use its domain as filename.
        if record.website:
            try:
                url = record.website
                if not url.startswith(('http://', 'https://')):
                    url = 'http://' + url
                domain = urlparse(url).netloc.replace("www.", "")
                return f"{domain.split('.')[0]}.png"
            except Exception:
                return ""

        # Rule: If only socials found, use merchant name.
        if record.socials and record.cleaned_merchant_name:
            safe_name = "".join(re.findall(r'\w+', record.cleaned_merchant_name))
            return f"{safe_name}.png"

        # Rule: If neither found, leave blank.
        return ""

    def _build_search_queries(self, cleaned_name: str, record: MerchantRecord) -> List[str]:
        """Constructs the 6-step search queries, ensuring the cleaned name is used."""
        name = cleaned_name or record.original_name # Fallback to original if cleaning fails
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

        return list(dict.fromkeys(queries)) # Return unique queries in order

    def _choose_best_social_link(self, candidates: List[str]) -> Optional[str]:
        """
        From a list of social media URLs, picks the best one.
        For now, this is a simple "first is best" implementation.
        Future enhancement could involve more logic (e.g., matching profile name).
        """
        if not candidates:
            return None
        # Simple heuristic: prefer well-known platforms
        for platform in ["facebook", "linkedin", "instagram", "twitter"]:
            for url in candidates:
                if platform in url:
                    return url
        return candidates[0]