import unittest
from unittest.mock import patch, MagicMock

from src.core.processing_engine import ProcessingEngine
from src.core.data_model import JobSettings, ColumnMapping, ApiConfig, MerchantRecord
from src.services.google_api_client import GoogleApiClient

class TestAILogic(unittest.TestCase):

    def setUp(self):
        self.settings = JobSettings(
            input_filepath="", output_filepath="",
            column_mapping=ColumnMapping(merchant_name="name"),
            start_row=2, end_row=2, mode="Basic", model_name="mock-model",
            mock_mode=True
        )
        self.api_config = ApiConfig()

    @patch('src.services.google_api_client.GoogleApiClient')
    def test_ai_accepts_valid_match(self, MockApiClient):
        """Verify the engine correctly processes a result where the AI finds a valid name."""
        mock_api_client = MockApiClient.return_value
        mock_api_client.remove_aggregators.return_value = ({"cleaned_name": "Good Mart", "removal_reason": "No aggregator found."}, "prompt")
        mock_api_client.search_web.return_value = [{"title": "Good Mart", "link": "http://goodmart.com", "snippet": "Official site for Good Mart"}]
        mock_api_client.analyze_search_results.return_value = ({"cleaned_merchant_name": "Good Mart", "website_candidate": "http://goodmart.com", "social_media_candidate": "", "business_status": "Operational", "supporting_evidence": "Official site for Good Mart"}, "prompt")
        mock_api_client.verify_website_with_ai.return_value = ({"is_valid": True, "reasoning": "Site looks valid."}, "prompt")

        engine = ProcessingEngine(self.settings, mock_api_client, lambda *args: "mock content")
        record = MerchantRecord(original_name="Good Mart")
        processed_record = engine.process_record(record)

        self.assertEqual(processed_record.cleaned_merchant_name, "Good Mart")
        self.assertEqual(processed_record.website, "http://goodmart.com")
        self.assertEqual(processed_record.remarks, "")
        self.assertEqual(processed_record.socials, [])

    @patch('src.services.google_api_client.GoogleApiClient')
    def test_ai_rejects_mismatched_result(self, MockApiClient):
        """Verify the engine rejects a result where the AI finds no valid name."""
        mock_api_client = MockApiClient.return_value
        mock_api_client.remove_aggregators.return_value = ({"cleaned_name": "Shady LLC", "removal_reason": "No aggregator found."}, "prompt")
        mock_api_client.search_web.return_value = [{"title": "Some Other Business", "link": "http://other.com", "snippet": "We sell different things"}]
        # The AI, following the rules, returns an empty name because the evidence doesn't match.
        mock_api_client.analyze_search_results.return_value = ({"cleaned_merchant_name": "", "website_candidate": "", "social_media_candidate": "", "business_status": "Uncertain", "supporting_evidence": "No direct evidence found in search results."}, "prompt")

        engine = ProcessingEngine(self.settings, mock_api_client, lambda *args: "mock content")
        record = MerchantRecord(original_name="Shady LLC")
        processed_record = engine.process_record(record)

        self.assertEqual(processed_record.cleaned_merchant_name, "")
        self.assertEqual(processed_record.website, "")
        self.assertEqual(processed_record.remarks, "NA")
        self.assertIn("No merchant name found by AI", processed_record.evidence)

if __name__ == '__main__':
    unittest.main()