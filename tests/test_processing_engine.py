import unittest
from unittest.mock import Mock, patch, MagicMock

from src.core.data_model import MerchantRecord, JobSettings, ApiConfig, ColumnMapping
from src.core.processing_engine import ProcessingEngine, API_COSTS
from src.services.google_api_client import GoogleApiClient

class TestProcessingEngine(unittest.TestCase):

    def setUp(self):
        """Set up a mock API client and default settings for each test."""
        self.mock_api_config = ApiConfig(
            gemini_api_key="fake_gemini",
            search_api_key="fake_search",
            places_api_key="fake_places" # Available for enhanced mode tests
        )
        self.mock_api_client = Mock(spec=GoogleApiClient)
        self.mock_api_client.api_config = self.mock_api_config

        # Default mock returns for API calls to avoid failures on non-tested calls
        self.mock_api_client.clean_merchant_name.return_value = {
            "cleaned_name": "Test Merchant Cleaned",
            "reasoning": "Mocked cleaning"
        }
        self.mock_api_client.search_web.return_value = None
        self.mock_api_client.find_place.return_value = None

        # Dummy job settings
        self.job_settings = JobSettings(
            input_filepath="dummy.xlsx",
            output_filepath="dummy_out.xlsx",
            column_mapping=Mock(spec=ColumnMapping),
            start_row=2, end_row=100,
            mode="Basic" # Default to basic mode
        )

    def test_basic_mode_successful_search(self):
        """Test a successful workflow in Basic mode using Google Search."""
        self.job_settings.mode = "Basic"
        engine = ProcessingEngine(self.job_settings, self.mock_api_client)

        # Simulate search finding a result on the second query
        search_query_2 = "Test Merchant Cleaned Anytown USA"
        successful_search_result = [{"title": "Official Site", "link": "http://testmerchant.com", "snippet": "Welcome"}]
        self.mock_api_client.search_web.side_effect = [
            None,  # First query fails
            successful_search_result # Second query succeeds
        ]

        record = MerchantRecord(original_name="TEST MERCHANT", original_city="Anytown", original_country="USA")
        processed = engine.process_record(record)

        # Verify find_place was NOT called
        self.mock_api_client.find_place.assert_not_called()

        # Verify search was called (at least twice)
        self.assertEqual(self.mock_api_client.search_web.call_count, 2)

        # Verify record is populated correctly
        self.assertEqual(processed.cleaned_merchant_name, "Test Merchant Cleaned")
        self.assertEqual(processed.website, "http://testmerchant.com")
        self.assertIn("Found via Google Search", processed.evidence)

        # Verify cost calculation
        expected_cost = API_COSTS["gemini_flash_per_request"] + (2 * API_COSTS["google_search_per_query"])
        self.assertAlmostEqual(processed.cost_per_row, expected_cost)

    def test_enhanced_mode_successful_places_search(self):
        """Test a successful workflow in Enhanced mode using Google Places."""
        self.job_settings.mode = "Enhanced"
        engine = ProcessingEngine(self.job_settings, self.mock_api_client)

        # Simulate Places API finding a result on the first query
        successful_places_result = {
            "status": "OK",
            "results": [{
                "name": "Test Merchant Official Name",
                "website": "http://places-merchant.com"
            }]
        }
        self.mock_api_client.find_place.return_value = successful_places_result

        record = MerchantRecord(original_name="TEST MERCHANT", original_city="Anytown", original_country="USA")
        processed = engine.process_record(record)

        # Verify Places API was called
        self.mock_api_client.find_place.assert_called_once()

        # Verify Search API was NOT called
        self.mock_api_client.search_web.assert_not_called()

        # Verify record is populated correctly
        self.assertEqual(processed.website, "http://places-merchant.com")
        self.assertIn("Found via Google Places", processed.evidence)

        # Verify cost calculation
        expected_cost = API_COSTS["gemini_flash_per_request"] + API_COSTS["google_places_find_place"]
        self.assertAlmostEqual(processed.cost_per_row, expected_cost)

    def test_enhanced_mode_fallback_to_search(self):
        """Test Enhanced mode falling back to Search when Places API finds no match."""
        self.job_settings.mode = "Enhanced"
        engine = ProcessingEngine(self.job_settings, self.mock_api_client)

        # Simulate Places API failing and Search API succeeding
        self.mock_api_client.find_place.return_value = {"status": "ZERO_RESULTS"}
        self.mock_api_client.search_web.return_value = [{"title": "Search Fallback", "link": "http://search-fallback.com"}]

        record = MerchantRecord(original_name="TEST MERCHANT", original_city="Anytown", original_country="USA")
        processed = engine.process_record(record)

        # Verify both Places and Search were called
        self.assertTrue(self.mock_api_client.find_place.call_count > 0)
        self.assertTrue(self.mock_api_client.search_web.call_count > 0)

        # Verify record is populated from search result
        self.assertEqual(processed.website, "http://search-fallback.com")
        self.assertIn("Found via Google Search", processed.evidence)

        # Cost should include all attempts
        expected_cost = API_COSTS["gemini_flash_per_request"] + \
                        (self.mock_api_client.find_place.call_count * API_COSTS["google_places_find_place"]) + \
                        (self.mock_api_client.search_web.call_count * API_COSTS["google_search_per_query"])
        self.assertAlmostEqual(processed.cost_per_row, expected_cost)

    def test_no_match_found(self):
        """Test the case where no search method finds a result."""
        engine = ProcessingEngine(self.job_settings, self.mock_api_client)

        # All APIs return no results
        self.mock_api_client.search_web.return_value = None
        self.mock_api_client.find_place.return_value = None

        record = MerchantRecord(original_name="OBSCURE BIZ", original_city="Nowhere")
        processed = engine.process_record(record)

        self.assertEqual(processed.website, "")
        self.assertEqual(processed.evidence, "No match found.")
        self.assertIn("No definitive website found", processed.remarks)

    def test_logo_filename_generation(self):
        """Test the logo filename generation logic."""
        engine = ProcessingEngine(self.job_settings, self.mock_api_client)
        record = MerchantRecord(original_name="My Awesome Store!")
        processed = engine.process_record(record)

        # The cleaned name is "Test Merchant Cleaned" from the mock
        self.assertEqual(processed.logo_filename, "test_merchant_cleaned_logo.png")

if __name__ == '__main__':
    unittest.main()