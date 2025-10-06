import unittest
from unittest.mock import Mock, MagicMock

from src.core.data_model import MerchantRecord, JobSettings, ApiConfig, ColumnMapping
from src.core.processing_engine import ProcessingEngine
from src.core.cost_estimator import CostEstimator

class TestProcessingEngine(unittest.TestCase):

    def setUp(self):
        """Set up a mock API client and default settings for each test."""
        self.mock_api_config = ApiConfig("fake_gemini", "fake_search", "fake_cse", "fake_places")
        self.mock_api_client = MagicMock()
        self.mock_api_client.api_config = self.mock_api_config
        # Default mock for the AI data extraction
        self.mock_api_client.validate_and_enrich_from_search.return_value = {
            "best_match_title": "", "found_merchant_name": "", "website": "",
            "social_media_links": [], "evidence_summary": "AI could not find a confident match.",
            "is_likely_official": False, "is_closed": False, "is_aggregator": False, "is_social_media": False
        }
        self.job_settings = JobSettings(
            input_filepath="dummy.xlsx", output_filepath="dummy_out.xlsx",
            column_mapping=Mock(spec=ColumnMapping), start_row=2, end_row=100,
            mode="Basic", model_name="models/gemini-test"
        )
        CostEstimator.get_model_cost = Mock(return_value=0.001)

    def test_basic_mode_successful_search_finds_website(self):
        """Test a successful workflow in Basic mode that finds an official website."""
        engine = ProcessingEngine(self.job_settings, self.mock_api_client)
        self.mock_api_client.search_web.return_value = [{"title": "Official Site"}]
        self.mock_api_client.validate_and_enrich_from_search.return_value = {
            "found_merchant_name": "Test Merchant", "website": "http://testmerchant.com",
            "is_likely_official": True, "is_closed": False, "is_aggregator": False, "is_social_media": False
        }
        record = MerchantRecord(original_name="* 123 TEST MERCHANT")
        processed = engine.process_record(record)
        self.assertEqual(processed.website, "http://testmerchant.com")
        self.assertEqual(processed.socials, [])
        self.assertEqual(processed.remarks, "")
        self.assertEqual(processed.logo_filename, "testmerchant.png")
        self.assertIn("inspected and confirmed as a live, dedicated business site", processed.evidence)

    def test_enhanced_mode_successful_places_search(self):
        """Test a successful workflow in Enhanced mode using Google Places."""
        self.job_settings.mode = "Enhanced"
        engine = ProcessingEngine(self.job_settings, self.mock_api_client)
        self.mock_api_client.find_place.return_value = {
            "status": "OK", "results": [{"name": "Test Merchant From Places", "website": "http://places.com"}]
        }
        record = MerchantRecord(original_name="TEST MERCHANT")
        processed = engine.process_record(record)
        self.assertEqual(processed.website, "http://places.com")
        self.assertEqual(processed.cleaned_merchant_name, "Test Merchant From Places")
        self.assertIn("via Google Places", processed.evidence)
        self.assertEqual(processed.logo_filename, "places.png")

    def test_fallback_to_search_and_finds_socials(self):
        """Test Enhanced mode falling back to Search and finding only social media."""
        self.job_settings.mode = "Enhanced"
        engine = ProcessingEngine(self.job_settings, self.mock_api_client)
        self.mock_api_client.find_place.return_value = {"status": "ZERO_RESULTS"}
        self.mock_api_client.search_web.return_value = [{"title": "Social Page"}]
        self.mock_api_client.validate_and_enrich_from_search.return_value = {
            "found_merchant_name": "Test Merchant", "website": "http://facebook.com/test",
            "social_media_links": ["http://instagram.com/test"],
            "is_likely_official": True, "is_social_media": True
        }
        record = MerchantRecord(original_name="TEST MERCHANT")
        processed = engine.process_record(record)
        self.assertEqual(processed.website, "")
        self.assertIn("http://facebook.com/test", processed.socials)
        self.assertEqual(processed.remarks, "website unavailable")
        self.assertIn("Matched on an official social media page", processed.evidence)

    def test_no_match_found_after_all_searches(self):
        """Test the case where no search method finds a valid result."""
        engine = ProcessingEngine(self.job_settings, self.mock_api_client)
        self.mock_api_client.search_web.return_value = [{"title": "irrelevant"}]
        # This setup simulates the AI returning a result that is then rejected by our logic
        self.mock_api_client.validate_and_enrich_from_search.return_value = {
             "found_merchant_name": "Wrong Biz", "website": "http://irrelevant.com",
             "is_likely_official": True
        }
        processed = engine.process_record(MerchantRecord(original_name="OBSCURE BIZ"))
        self.assertEqual(processed.cleaned_merchant_name, "")
        self.assertEqual(processed.remarks, "Low confidence match (50%). Manual review required.")

    def test_business_found_but_is_closed(self):
        """Test that a business reported as closed is rejected."""
        engine = ProcessingEngine(self.job_settings, self.mock_api_client)
        self.mock_api_client.search_web.return_value = [{"title": "Closed Store"}]
        self.mock_api_client.validate_and_enrich_from_search.return_value = {
            "found_merchant_name": "My Old Store", "website": "http://myoldstore.com",
            "is_likely_official": True, "is_closed": True
        }
        processed = engine.process_record(MerchantRecord(original_name="My Old Store"))
        self.assertEqual(processed.cleaned_merchant_name, "")
        self.assertEqual(processed.remarks, "Business found but is permanently closed.")
        self.assertIn("Business is permanently closed", processed.evidence)

    def test_logo_filename_generation_logic(self):
        """Test the logo filename generation logic for website and social cases."""
        engine = ProcessingEngine(self.job_settings, self.mock_api_client)
        record = MerchantRecord(original_name="My Awesome Store!")
        # Case 1: Website is found
        record.website = "https://www.my-awesome-store.co.uk"
        record.socials = []
        record.cleaned_merchant_name = "My Awesome Store"
        self.assertEqual(engine._generate_logo_filename(record), "my-awesome-store.png")
        # Case 2: Only socials are found
        record.website = ""
        record.socials = ["http://facebook.com/mystore"]
        self.assertEqual(engine._generate_logo_filename(record), "myawesomestore.png")
        # Case 3: Neither is found
        record.socials = []
        self.assertEqual(engine._generate_logo_filename(record), "")

if __name__ == '__main__':
    unittest.main()