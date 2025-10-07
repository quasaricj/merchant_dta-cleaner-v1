import unittest
from unittest.mock import MagicMock, patch
from src.core.processing_engine import ProcessingEngine
from src.core.data_model import JobSettings, MerchantRecord, ColumnMapping, ApiConfig

class TestProcessingEngine(unittest.TestCase):

    def setUp(self):
        """Set up common objects for testing the processing engine."""
        self.job_settings = JobSettings(
            input_filepath="dummy.xlsx",
            output_filepath="dummy_out.xlsx",
            column_mapping=ColumnMapping(merchant_name="Name"),
            start_row=1,
            end_row=1,
            mode="Basic",
            model_name="gemini-1.5-flash"
        )
        self.mock_api_client = MagicMock()
        self.mock_view_text_website = MagicMock(return_value="<html>Valid content</html>")

    def test_successful_website_found(self):
        """Test a successful workflow where the AI finds a valid website."""
        # Arrange
        self.mock_api_client.search_web.return_value = [{"title": "Official Site", "link": "http://example.com"}]
        self.mock_api_client.analyze_search_results.return_value = {
            "cleaned_merchant_name": "Example Corp",
            "website": "http://example.com",
            "social_media_links": [],
            "evidence": "Found official website.",
            "status": "MATCH_FOUND"
        }
        engine = ProcessingEngine(self.job_settings, self.mock_api_client, self.mock_view_text_website)
        record = MerchantRecord(original_name="EXAMPLE", cleaned_merchant_name="EXAMPLE")

        # Act
        result = engine.process_record(record)

        # Assert
        self.assertEqual(result.cleaned_merchant_name, "Example Corp")
        self.assertEqual(result.website, "http://example.com")
        self.assertEqual(result.socials, [])
        self.assertEqual(result.remarks, "")
        self.assertEqual(result.logo_filename, "example.png")
        self.assertIn("Found official website.", result.evidence)

    def test_successful_socials_found(self):
        """Test a successful workflow where the AI only finds social media links."""
        # Arrange
        self.mock_api_client.search_web.return_value = [{"title": "Facebook Page", "link": "http://facebook.com/example"}]
        self.mock_api_client.analyze_search_results.return_value = {
            "cleaned_merchant_name": "Example Corp",
            "website": "",
            "social_media_links": ["http://facebook.com/example"],
            "evidence": "Found official social media.",
            "status": "MATCH_FOUND"
        }
        engine = ProcessingEngine(self.job_settings, self.mock_api_client, self.mock_view_text_website)
        record = MerchantRecord(original_name="EXAMPLE", cleaned_merchant_name="EXAMPLE")

        # Act
        result = engine.process_record(record)

        # Assert
        self.assertEqual(result.cleaned_merchant_name, "Example Corp")
        self.assertEqual(result.website, "")
        self.assertEqual(result.socials, ["http://facebook.com/example"])
        self.assertEqual(result.remarks, "website unavailable")
        self.assertEqual(result.logo_filename, "examplecorp.png")

    def test_ai_rejects_match(self):
        """Test the case where the AI analyzes results but rejects them as invalid."""
        # Arrange
        self.mock_api_client.search_web.return_value = [{"title": "Some other business", "link": "http://other.com"}]
        self.mock_api_client.analyze_search_results.return_value = {
            "cleaned_merchant_name": "",
            "website": "",
            "social_media_links": [],
            "evidence": "Business is permanently closed.",
            "status": "BUSINESS_CLOSED"
        }
        engine = ProcessingEngine(self.job_settings, self.mock_api_client, self.mock_view_text_website)
        record = MerchantRecord(original_name="EXAMPLE", cleaned_merchant_name="EXAMPLE")

        # Act
        result = engine.process_record(record)

        # Assert
        self.assertEqual(result.cleaned_merchant_name, "")
        self.assertEqual(result.website, "")
        self.assertEqual(result.remarks, "NA")
        self.assertIn("permanently closed", result.evidence)

    def test_no_search_results_found(self):
        """Test the case where Google search returns no results."""
        # Arrange
        self.mock_api_client.search_web.return_value = None
        self.mock_api_client.analyze_search_results.return_value = None # Should not be called
        engine = ProcessingEngine(self.job_settings, self.mock_api_client, self.mock_view_text_website)
        record = MerchantRecord(original_name="UNKNOWNBIZ", cleaned_merchant_name="UNKNOWNBIZ")

        # Act
        result = engine.process_record(record)

        # Assert
        self.assertEqual(result.cleaned_merchant_name, "")
        self.assertEqual(result.remarks, "NA")
        self.assertIn("No valid business match found", result.evidence)
        self.mock_api_client.analyze_search_results.assert_not_called()

    def test_logo_filename_generation_logic(self):
        """Test the logo filename generation logic for website and social cases."""
        # Arrange
        engine = ProcessingEngine(self.job_settings, self.mock_api_client, self.mock_view_text_website)

        # Test website case
        record_web = MerchantRecord(original_name="web", cleaned_merchant_name="Web Inc", website="http://www.web-inc.co.uk")
        filename_web = engine._generate_logo_filename(record_web)
        self.assertEqual(filename_web, "web-inc.png")

        # Test social media case
        record_social = MerchantRecord(original_name="social", cleaned_merchant_name="Social Company", socials=["http://facebook.com/social"])
        filename_social = engine._generate_logo_filename(record_social)
        self.assertEqual(filename_social, "socialcompany.png")

        # Test no website or social case
        record_none = MerchantRecord(original_name="none", cleaned_merchant_name="No Media")
        filename_none = engine._generate_logo_filename(record_none)
        self.assertEqual(filename_none, "")

    def test_website_overrides_socials_rule(self):
        """
        Test that finding a website correctly clears the social media links,
        even if the AI analysis provided both.
        """
        # Arrange: AI analysis returns both a website and social links
        self.mock_api_client.search_web.return_value = [{"title": "Official Site", "link": "http://example.com"}]
        self.mock_api_client.analyze_search_results.return_value = {
            "cleaned_merchant_name": "Example Corp",
            "website": "http://example.com",
            "social_media_links": ["http://facebook.com/example"], # AI found this
            "evidence": "Found official website and a social page.",
            "status": "MATCH_FOUND"
        }
        engine = ProcessingEngine(self.job_settings, self.mock_api_client, self.mock_view_text_website)
        record = MerchantRecord(original_name="EXAMPLE", cleaned_merchant_name="EXAMPLE")

        # Act
        result = engine.process_record(record)

        # Assert: The business rule should prioritize the website and clear socials.
        self.assertEqual(result.website, "http://example.com")
        self.assertEqual(result.socials, [], "Socials should be empty if a website is found.")
        self.assertEqual(result.remarks, "", "Remarks should be empty on successful website match.")

if __name__ == '__main__':
    unittest.main()