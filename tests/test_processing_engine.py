import unittest
from unittest.mock import MagicMock
from src.core.processing_engine import ProcessingEngine
from src.core.data_model import JobSettings, MerchantRecord, ColumnMapping

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
        # Mock the view_text_website function to simulate a valid, working website
        self.mock_view_text_website = MagicMock(return_value="<html><body>Official Business Content</body></html>")

    def test_successful_website_found(self):
        """Test a successful workflow where the AI finds a valid website."""
        # Arrange
        self.mock_api_client.search_web.return_value = [{"title": "Official Site", "link": "http://example.com"}]
        self.mock_api_client.analyze_search_results.return_value = {
            "cleaned_merchant_name": "Example Corp",
            "website": "http://example.com",
            "social_media_links": [],
            "business_status": "Operational",
            "match_type": "Exact Match",
            "evidence": "Found official website."
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
            "business_status": "Operational",
            "match_type": "Exact Match",
            "evidence": "Found official social media."
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

    def test_business_permanently_closed(self):
        """Test that a business marked 'Permanently Closed' is rejected."""
        # Arrange
        self.mock_api_client.search_web.return_value = [{"title": "Some business", "link": "http://other.com"}]
        self.mock_api_client.analyze_search_results.return_value = {
            "cleaned_merchant_name": "Old Business Inc",
            "website": "http://other.com",
            "social_media_links": [],
            "business_status": "Permanently Closed",
            "match_type": "Exact Match",
            "evidence": "Business is permanently closed."
        }
        engine = ProcessingEngine(self.job_settings, self.mock_api_client, self.mock_view_text_website)
        record = MerchantRecord(original_name="EXAMPLE", cleaned_merchant_name="EXAMPLE")

        # Act
        result = engine.process_record(record)

        # Assert
        self.assertEqual(result.cleaned_merchant_name, "")
        self.assertEqual(result.website, "")
        self.assertEqual(result.remarks, "NA")
        self.assertIn("permanently closed", result.evidence.lower())

    def test_no_match_found(self):
        """Test the case where the AI finds no relevant match."""
        # Arrange
        self.mock_api_client.search_web.return_value = [{"title": "Irrelevant Site", "link": "http://unrelated.com"}]
        self.mock_api_client.analyze_search_results.return_value = {
            "cleaned_merchant_name": "",
            "website": "",
            "social_media_links": [],
            "business_status": "Uncertain",
            "match_type": "No Match",
            "evidence": "Could not find any relevant business information."
        }
        engine = ProcessingEngine(self.job_settings, self.mock_api_client, self.mock_view_text_website)
        record = MerchantRecord(original_name="OBSCURE BIZ", cleaned_merchant_name="OBSCURE BIZ")

        # Act
        result = engine.process_record(record)

        # Assert
        self.assertEqual(result.cleaned_merchant_name, "")
        self.assertEqual(result.remarks, "NA")
        self.assertIn("No valid business match was found", result.evidence)

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
            "business_status": "Operational",
            "match_type": "Exact Match",
            "evidence": "Found official website and a social page."
        }
        engine = ProcessingEngine(self.job_settings, self.mock_api_client, self.mock_view_text_website)
        record = MerchantRecord(original_name="EXAMPLE", cleaned_merchant_name="EXAMPLE")

        # Act
        result = engine.process_record(record)

        # Assert: The business rule should prioritize the website and clear socials.
        self.assertEqual(result.website, "http://example.com")
        self.assertEqual(result.socials, [], "Socials should be empty if a website is found.")
        self.assertEqual(result.remarks, "", "Remarks should be empty on successful website match.")

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

if __name__ == '__main__':
    unittest.main()