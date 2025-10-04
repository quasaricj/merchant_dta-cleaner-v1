import unittest
from unittest.mock import Mock, patch

from src.core.data_model import MerchantRecord, JobSettings, ApiConfig, ColumnMapping
from src.core.processing_engine import ProcessingEngine
from src.core.cost_estimator import API_COSTS, CostEstimator
from src.services.google_api_client import GoogleApiClient

class TestProcessingEngine(unittest.TestCase):

    def setUp(self):
        """Set up a mock API client and default settings for each test."""
        self.mock_api_config = ApiConfig(
            gemini_api_key="fake_gemini",
            search_api_key="fake_search",
            search_cse_id="fake_cse",
            places_api_key="fake_places"
        )
        self.mock_api_client = Mock(spec=GoogleApiClient)
        self.mock_api_client.api_config = self.mock_api_config

        self.mock_api_client.clean_merchant_name.return_value = {
            "cleaned_name": "Test Merchant Cleaned",
            "reasoning": "Mocked cleaning"
        }
        self.mock_api_client.search_web.return_value = None
        self.mock_api_client.find_place.return_value = None
        # Add a default mock for the new validation method to prevent unexpected failures
        self.mock_api_client.validate_and_enrich_from_search.return_value = {
            "official_website": "", "social_media_links": [], "evidence": "Mock: No match"
        }

        self.job_settings = JobSettings(
            input_filepath="dummy.xlsx",
            output_filepath="dummy_out.xlsx",
            column_mapping=Mock(spec=ColumnMapping),
            start_row=2, end_row=100,
            mode="Basic",
            model_name="models/gemini-2.0-flash" # Use a default model for tests
        )

    def test_basic_mode_successful_search(self):
        """Test a successful workflow in Basic mode using Google Search."""
        self.job_settings.mode = "Basic"
        engine = ProcessingEngine(self.job_settings, self.mock_api_client)
        successful_search_result = [{"title": "Official Site", "link": "http://testmerchant.com"}]
        self.mock_api_client.search_web.side_effect = [None, successful_search_result]

        successful_validation = {"official_website": "http://testmerchant.com", "social_media_links": [], "evidence": "Mocked success"}
        self.mock_api_client.validate_and_enrich_from_search.return_value = successful_validation

        record = MerchantRecord(original_name="TEST MERCHANT", original_city="Anytown", original_country="USA")

        processed = engine.process_record(record)

        self.assertEqual(self.mock_api_client.search_web.call_count, 2)
        self.mock_api_client.validate_and_enrich_from_search.assert_called_once()
        self.assertEqual(processed.website, "http://testmerchant.com")

        gemini_cost = CostEstimator.get_model_cost(self.job_settings.model_name)
        # Cost: 1x name cleaning (AI), 2x search queries, 1x validation (AI)
        expected_cost = gemini_cost + (2 * API_COSTS["google_search_per_query"]) + gemini_cost
        self.assertAlmostEqual(processed.cost_per_row, expected_cost)

    def test_enhanced_mode_successful_places_search(self):
        """Test a successful workflow in Enhanced mode using Google Places."""
        self.job_settings.mode = "Enhanced"
        engine = ProcessingEngine(self.job_settings, self.mock_api_client)
        successful_places_result = {"status": "OK", "results": [{"name": "Test Merchant", "website": "http://places.com"}]}
        self.mock_api_client.find_place.return_value = successful_places_result
        record = MerchantRecord(original_name="TEST MERCHANT")

        processed = engine.process_record(record)

        self.mock_api_client.find_place.assert_called_once()
        self.mock_api_client.search_web.assert_not_called()
        self.assertEqual(processed.website, "http://places.com")

        gemini_cost = CostEstimator.get_model_cost(self.job_settings.model_name)
        expected_cost = gemini_cost + API_COSTS["google_places_find_place"]
        self.assertAlmostEqual(processed.cost_per_row, expected_cost)

    def test_enhanced_mode_fallback_to_search(self):
        """Test Enhanced mode falling back to Search when Places API finds no match."""
        self.job_settings.mode = "Enhanced"
        engine = ProcessingEngine(self.job_settings, self.mock_api_client)
        self.mock_api_client.find_place.return_value = {"status": "ZERO_RESULTS"}
        self.mock_api_client.search_web.return_value = [{"title": "Fallback", "link": "http://fallback.com"}]

        successful_validation = {"official_website": "http://fallback.com", "social_media_links": [], "evidence": "Mocked fallback success"}
        self.mock_api_client.validate_and_enrich_from_search.return_value = successful_validation

        record = MerchantRecord(original_name="TEST MERCHANT")

        processed = engine.process_record(record)

        self.assertTrue(self.mock_api_client.find_place.call_count > 0)
        self.assertTrue(self.mock_api_client.search_web.call_count > 0)
        self.assertTrue(self.mock_api_client.validate_and_enrich_from_search.call_count > 0)
        self.assertEqual(processed.website, "http://fallback.com")

        gemini_cost = CostEstimator.get_model_cost(self.job_settings.model_name)
        expected_cost = (gemini_cost +
                         (self.mock_api_client.find_place.call_count * API_COSTS["google_places_find_place"]) +
                         (self.mock_api_client.search_web.call_count * API_COSTS["google_search_per_query"]) +
                         (self.mock_api_client.validate_and_enrich_from_search.call_count * gemini_cost))
        self.assertAlmostEqual(processed.cost_per_row, expected_cost)

    def test_no_match_found(self):
        """Test the case where no search method finds a result."""
        engine = ProcessingEngine(self.job_settings, self.mock_api_client)
        # We need search to return *something* to trigger the validation step.
        self.mock_api_client.search_web.return_value = [{"title": "some irrelevant result", "link": "http://example.com"}]
        # Ensure the validation method also reports no match
        self.mock_api_client.validate_and_enrich_from_search.return_value = {
            "official_website": "", "social_media_links": [], "evidence": "AI confirmed no match."
        }
        processed = engine.process_record(MerchantRecord(original_name="OBSCURE BIZ"))
        self.assertEqual(processed.website, "")
        self.assertEqual(processed.evidence, "AI confirmed no match.")

    def test_logo_filename_generation(self):
        """Test the logo filename generation logic."""
        engine = ProcessingEngine(self.job_settings, self.mock_api_client)
        processed = engine.process_record(MerchantRecord(original_name="My Awesome Store!"))
        self.assertEqual(processed.logo_filename, "test_merchant_cleaned_logo.png")

if __name__ == '__main__':
    unittest.main()