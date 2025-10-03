# pylint: disable=too-few-public-methods
"""
This module contains the core business logic for cleaning and enriching a single
merchant record. It orchestrates calls to the Google API client based on the
selected processing mode.
"""
from typing import List, Dict, Optional

from src.core.data_model import MerchantRecord, JobSettings
from src.services.google_api_client import GoogleApiClient
from src.core.cost_estimator import API_COSTS


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
        # 1. Clean the merchant name using AI
        self._clean_name_with_ai(record)

        # 2. Build search queries
        queries = self._build_search_queries(record)

        # 3. Execute search logic based on mode
        match_found = False
        for query in queries:
            if self.settings.mode == "Enhanced" and self.api_client.api_config.places_api_key:
                match_found = self._perform_enhanced_search(record, query)
            else:
                match_found = self._perform_basic_search(record, query)

            if match_found:
                break  # Stop on the first successful match

        if not record.website:
            record.remarks += " | No definitive website found after all search steps."
            record.evidence = "No match found."

        # 4. Finalize record
        record.logo_filename = self._generate_logo_filename(record.cleaned_merchant_name)

        return record

    def _clean_name_with_ai(self, record: MerchantRecord):
        """Uses AI to clean the merchant name and updates the record."""
        cleaned_info = self.api_client.clean_merchant_name(record.original_name)
        record.cost_per_row += API_COSTS["gemini_flash_per_request"]

        if cleaned_info and cleaned_info.get("cleaned_name"):
            record.cleaned_merchant_name = cleaned_info["cleaned_name"]
            record.remarks = f"AI Cleaning: {cleaned_info.get('reasoning', 'N/A')}"
        else:
            record.cleaned_merchant_name = record.original_name.strip()
            record.remarks = "AI cleaning failed; using original name."

    def _perform_enhanced_search(self, record: MerchantRecord, query: str) -> bool:
        """Performs a Places API search with a fallback to web search."""
        # Try Places API first
        place_result = self.api_client.find_place(query)
        record.cost_per_row += API_COSTS["google_places_find_place"]
        if self._is_valid_place_result(place_result):
            first_result = place_result["results"][0]  # type: ignore
            record.website = first_result.get("website", "")
            official_name = first_result.get("name", record.cleaned_merchant_name)
            record.evidence = f"Found via Google Places: '{official_name}' with query: '{query}'"
            record.evidence_links.append(
                f"https://www.google.com/maps/search/?api=1&query={query.replace(' ', '+')}"
            )
            return True
        # Fallback to web search
        return self._perform_basic_search(record, query)

    def _perform_basic_search(self, record: MerchantRecord, query: str) -> bool:
        """Performs a standard web search."""
        search_results = self.api_client.search_web(query)
        record.cost_per_row += API_COSTS["google_search_per_query"]
        if search_results:
            best_result = self._find_best_match(search_results, record.cleaned_merchant_name)
            if best_result:
                record.website = best_result.get("link", "")
                record.evidence = (
                    f"Found via Google Search with query: '{query}'. "
                    f"Title: '{best_result.get('title')}'"
                )
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
        """
        A simple heuristic to find the best search result.
        Prefers results where the title closely matches the cleaned name.
        """
        for result in results:
            if cleaned_name.lower() in result.get("title", "").lower():
                return result
        return results[0] if results else None

    def _generate_logo_filename(self, cleaned_name: str) -> str:
        """Creates a standardized logo filename (FR21)."""
        if not cleaned_name:
            return ""
        safe_name = "".join(c for c in cleaned_name if c.isalnum() or c in " _-").rstrip()
        return f"{safe_name.replace(' ', '_').lower()}_logo.png"

# Example usage
if __name__ == '__main__':
    from src.core.config_manager import load_api_config
    from src.core.data_model import ColumnMapping

    api_conf = load_api_config()
    if not api_conf:
        print("API config not found. Cannot run example.")
    else:
        client = GoogleApiClient(api_conf)
        job_settings = JobSettings(
            input_filepath="dummy.xlsx",
            output_filepath="dummy_out.xlsx",
            column_mapping=ColumnMapping(merchant_name="name"),
            start_row=2, end_row=100,
            mode="Enhanced"
        )

        engine = ProcessingEngine(job_settings, client)

        test_rec = MerchantRecord(
            original_name="STARBUCKS #12345",
            original_city="Seattle",
            original_country="USA"
        )

        processed_rec = engine.process_record(test_rec)

        print("--- Processed Record ---")
        print(f"Cleaned Name: {processed_rec.cleaned_merchant_name}")
        print(f"Website: {processed_rec.website}")
        print(f"Evidence: {processed_rec.evidence}")
        print(f"Evidence Links: {processed_rec.evidence_links}")
        print(f"Cost: {processed_rec.cost_per_row:.4f}")
        print(f"Remarks: {processed_rec.remarks}")
        print(f"Logo Filename: {processed_rec.logo_filename}")