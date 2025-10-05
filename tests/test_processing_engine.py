import unittest
from unittest.mock import Mock, MagicMock

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
        # Use MagicMock to handle attribute assignment on the mock
        self.mock_api_client = MagicMock(spec=GoogleApiClient)
        self.mock_api_client.api_config = self.mock_api_config

        # Default mock for AI name cleaning
        self.mock_api_client.clean_merchant_name.return_value = {
            "cleaned_name": "Test Merchant Cleaned",
            "reasoning": "Mocked cleaning"
        }

        # Default mocks for search APIs - they will be overridden in specific tests
        self.mock_api_client.search_web.return_value = None
        self.mock_api_client.find_place.return_value = None

        # Default mock for the AI data extraction - returns an empty/non-match result
        self.mock_api_client.validate_and_enrich_from_search.return_value = {
            "best_match_title": "",
            "found_merchant_name": "",
            "website": "",
            "social_media_links": [],
            "evidence_summary": "AI could not find a confident match.",
            "is_likely_official": False,
            "is_closed": False,
            "is_aggregator": False,
            "is_social_media": False
        }

        self.job_settings = JobSettings(
            input_filepath="dummy.xlsx",
            output_filepath="dummy_out.xlsx",
            column_mapping=Mock(spec=ColumnMapping),
            start_row=2, end_row=100,
            mode="Basic",
            model_name="models/gemini-1.0-pro" # Using a known model for consistent cost calculation
        )
        # Mock the cost estimator to avoid dependency on the actual cost values
        CostEstimator.get_model_cost = Mock(return_value=0.001)


    def test_basic_mode_successful_search_finds_website(self):
        """Test a successful workflow in Basic mode that finds an official website."""
        self.job_settings.mode = "Basic"
        engine = ProcessingEngine(self.job_settings, self.mock_api_client)

        # Mock search_web to return a result on the first call
        self.mock_api_client.search_web.return_value = [{"title": "Official Site", "link": "http://testmerchant.com"}]

        # Mock AI extraction to return a confident, official website match
        self.mock_api_client.validate_and_enrich_from_search.return_value = {
            "best_match_title": "Official Site",
            "found_merchant_name": "Test Merchant Cleaned",
            "website": "http://testmerchant.com",
            "social_media_links": [],
            "evidence_summary": "Result #1 is the official site.",
            "is_likely_official": True,
            "is_closed": False,
            "is_aggregator": False,
            "is_social_media": False
        }

        record = MerchantRecord(original_name="TEST MERCHANT", original_city="Anytown", original_country="USA")
        processed = engine.process_record(record)

        # Assertions
        self.mock_api_client.search_web.assert_called_once()
        self.mock_api_client.validate_and_enrich_from_search.assert_called_once()
        self.assertEqual(processed.website, "http://testmerchant.com")
        self.assertEqual(processed.socials, []) # Socials should be blank if website is found
        self.assertEqual(processed.remarks, "") # Remarks should be blank on success
        self.assertEqual(processed.logo_filename, "testmerchant.png")
        self.assertIn("Result #1 is the official site", processed.evidence)
        self.assertTrue(len(processed.evidence_links) > 0)

    def test_enhanced_mode_successful_places_search(self):
        """Test a successful workflow in Enhanced mode using Google Places."""
        self.job_settings.mode = "Enhanced"
        engine = ProcessingEngine(self.job_settings, self.mock_api_client)

        successful_places_result = {
            "status": "OK",
            "results": [{"name": "Test Merchant From Places", "website": "http://places.com"}]
        }
        self.mock_api_client.find_place.return_value = successful_places_result
        record = MerchantRecord(original_name="TEST MERCHANT")

        processed = engine.process_record(record)

        self.mock_api_client.find_place.assert_called_once()
        self.mock_api_client.search_web.assert_not_called() # Should not fallback to web search
        self.assertEqual(processed.website, "http://places.com")
        self.assertEqual(processed.cleaned_merchant_name, "Test Merchant From Places")
        self.assertIn("Found via Google Places", processed.evidence)
        self.assertEqual(processed.logo_filename, "places.png")

    def test_fallback_to_search_and_finds_socials(self):
        """Test Enhanced mode falling back to Search and finding only social media."""
        self.job_settings.mode = "Enhanced"
        engine = ProcessingEngine(self.job_settings, self.mock_api_client)

        # Mock Places to return no results
        self.mock_api_client.find_place.return_value = {"status": "ZERO_RESULTS"}
        # Mock Search to return some results
        self.mock_api_client.search_web.return_value = [{"title": "Social Page", "link": "http://facebook.com/test"}]

        # Mock AI extraction to identify the result as a social media page
        self.mock_api_client.validate_and_enrich_from_search.return_value = {
            "best_match_title": "Social Page",
            "found_merchant_name": "Test Merchant Cleaned",
            "website": "http://facebook.com/test",
            "social_media_links": ["http://instagram.com/test"],
            "evidence_summary": "Result #1 is a Facebook page.",
            "is_likely_official": True, # It's officially their social page
            "is_closed": False,
            "is_aggregator": False,
            "is_social_media": True # Crucial flag
        }

        record = MerchantRecord(original_name="TEST MERCHANT")
        processed = engine.process_record(record)

        self.assertTrue(self.mock_api_client.find_place.call_count > 0)
        self.assertTrue(self.mock_api_client.search_web.call_count > 0)
        self.assertEqual(processed.website, "") # Website must be blank
        self.assertIn("http://facebook.com/test", processed.socials)
        self.assertIn("http://instagram.com/test", processed.socials)
        self.assertEqual(processed.remarks, "website unavailable")
        self.assertEqual(processed.logo_filename, "testmerchantcleaned.png")
        self.assertIn("Source is a social media page", processed.evidence)

    def test_no_match_found_after_all_searches(self):
        """Test the case where no search method finds a valid result."""
        engine = ProcessingEngine(self.job_settings, self.mock_api_client)

        # Mock all search attempts to return nothing or invalid data
        self.mock_api_client.search_web.return_value = [{"title": "irrelevant"}]
        self.mock_api_client.validate_and_enrich_from_search.return_value = {
            "best_match_title": "irrelevant",
            "found_merchant_name": "Some Biz",
            "website": "http://irrelevant.com",
            "social_media_links": [],
            "evidence_summary": "Could not verify this is the correct business.",
            "is_likely_official": False, # Crucial flag
            "is_closed": False,
            "is_aggregator": False,
            "is_social_media": False
        }

        processed = engine.process_record(MerchantRecord(original_name="OBSCURE BIZ"))

        self.assertEqual(processed.cleaned_merchant_name, "") # Should be blank if no match
        self.assertEqual(processed.website, "")
        self.assertEqual(processed.socials, [])
        self.assertEqual(processed.remarks, "NA")
        self.assertIn("not deemed an official", processed.evidence)

    def test_business_found_but_is_closed(self):
        """Test that a business reported as closed is rejected."""
        engine = ProcessingEngine(self.job_settings, self.mock_api_client)
        self.mock_api_client.search_web.return_value = [{"title": "Closed Store"}]
        self.mock_api_client.validate_and_enrich_from_search.return_value = {
            "best_match_title": "Closed Store",
            "found_merchant_name": "My Old Store",
            "website": "http://myoldstore.com",
            "evidence_summary": "This business is permanently closed.",
            "is_likely_official": True,
            "is_closed": True, # Crucial flag
            "is_aggregator": False,
            "is_social_media": False
        }

        processed = engine.process_record(MerchantRecord(original_name="My Old Store"))

        self.assertEqual(processed.cleaned_merchant_name, "") # Blank because it's an invalid match
        self.assertEqual(processed.website, "")
        self.assertEqual(processed.remarks, "NA")
        self.assertIn("reported as permanently closed", processed.evidence)

    def test_logo_filename_generation_logic(self):
        """Test the logo filename generation logic for website and social cases."""
        engine = ProcessingEngine(self.job_settings, self.mock_api_client)
        record = MerchantRecord(original_name="My Awesome Store!")

        # Case 1: Website is found
        record.website = "https://www.my-awesome-store.co.uk"
        record.socials = []
        record.cleaned_merchant_name = "My Awesome Store"
        logo_name = engine._generate_logo_filename(record)
        self.assertEqual(logo_name, "my-awesome-store.png")

        # Case 2: Only socials are found
        record.website = ""
        record.socials = ["http://facebook.com/mystore"]
        record.cleaned_merchant_name = "My Awesome Store"
        logo_name = engine._generate_logo_filename(record)
        self.assertEqual(logo_name, "myawesomestore.png")

        # Case 3: Neither is found
        record.website = ""
        record.socials = []
        logo_name = engine._generate_logo_filename(record)
        self.assertEqual(logo_name, "")

if __name__ == '__main__':
    unittest.main()