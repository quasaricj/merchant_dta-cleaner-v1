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
        self.job_settings = JobSettings(
            input_filepath="dummy.xlsx", output_filepath="dummy_out.xlsx",
            column_mapping=Mock(spec=ColumnMapping), start_row=2, end_row=100,
            mode="Basic", model_name="models/gemini-test"
        )
        CostEstimator.get_model_cost = Mock(return_value=0.001)

    def test_successful_website_found(self):
        """Test a successful workflow where the AI finds a valid website."""
        engine = ProcessingEngine(self.job_settings, self.mock_api_client)
        self.mock_api_client.search_web.return_value = [{"title": "Official Site"}]
        # Simulate the AI returning a valid, complete record
        self.mock_api_client.validate_and_enrich_from_search.return_value = {
            "cleaned_merchant_name": "Test Merchant",
            "website": "http://testmerchant.com",
            "social_media_links": [],
            "evidence": "Found a great match on Result #1."
        }
        record = MerchantRecord(original_name="* 123 TEST MERCHANT")
        processed = engine.process_record(record)
        self.assertEqual(processed.website, "http://testmerchant.com")
        self.assertEqual(processed.socials, [])
        self.assertEqual(processed.remarks, "") # Should be blank on success
        self.assertEqual(processed.logo_filename, "testmerchant.png")
        self.assertEqual(processed.evidence, "Found a great match on Result #1.")

    def test_successful_socials_found(self):
        """Test a successful workflow where the AI only finds social media links."""
        engine = ProcessingEngine(self.job_settings, self.mock_api_client)
        self.mock_api_client.search_web.return_value = [{"title": "Social Page"}]
        self.mock_api_client.validate_and_enrich_from_search.return_value = {
            "cleaned_merchant_name": "Test Merchant",
            "website": "",
            "social_media_links": ["http://facebook.com/test"],
            "evidence": "Could not find a website, but found a social media page."
        }
        record = MerchantRecord(original_name="TEST MERCHANT")
        processed = engine.process_record(record)
        self.assertEqual(processed.website, "")
        self.assertEqual(processed.socials, ["http://facebook.com/test"])
        self.assertEqual(processed.remarks, "website unavailable")
        self.assertEqual(processed.logo_filename, "TestMerchant.png") # Based on name
        self.assertEqual(processed.evidence, "Could not find a website, but found a social media page.")

    def test_ai_rejects_match(self):
        """Test the case where the AI analyzes results but rejects them as invalid."""
        engine = ProcessingEngine(self.job_settings, self.mock_api_client)
        self.mock_api_client.search_web.return_value = [{"title": "Irrelevant Site"}]
        # Simulate the AI rejecting the match
        self.mock_api_client.validate_and_enrich_from_search.return_value = {
            "cleaned_merchant_name": "",
            "website": "",
            "social_media_links": [],
            "evidence": "The search results were not relevant to the merchant."
        }
        record = MerchantRecord(original_name="OBSCURE BIZ")
        processed = engine.process_record(record)
        self.assertEqual(processed.website, "")
        self.assertEqual(processed.cleaned_merchant_name, "")
        self.assertEqual(processed.remarks, "NA")
        self.assertEqual(processed.evidence, "The search results were not relevant to the merchant.")

    def test_no_search_results_found(self):
        """Test the case where Google search returns no results."""
        engine = ProcessingEngine(self.job_settings, self.mock_api_client)
        self.mock_api_client.search_web.return_value = None # No results
        record = MerchantRecord(original_name="NON EXISTENT BIZ")
        processed = engine.process_record(record)
        self.assertEqual(processed.website, "")
        self.assertEqual(processed.cleaned_merchant_name, "")
        self.assertEqual(processed.remarks, "NA")
        self.assertIn("No valid business match found", processed.evidence)

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
        record.cleaned_merchant_name = "My Awesome Store"
        self.assertEqual(engine._generate_logo_filename(record), "MyAwesomeStore.png")
        # Case 3: Neither is found
        record.socials = []
        self.assertEqual(engine._generate_logo_filename(record), "")

if __name__ == '__main__':
    unittest.main()