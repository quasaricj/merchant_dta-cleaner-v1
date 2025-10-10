import unittest
import requests
from unittest.mock import MagicMock, patch
from src.core.processing_engine import ProcessingEngine
from src.core.data_model import JobSettings, MerchantRecord, ColumnMapping
from src import tools # Import the actual tools module

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

        # Configure the default mock for aggregator removal
        self.mock_api_client.remove_aggregators.return_value = {
            "cleaned_name": "Test Merchant", "removal_reason": "No aggregator found."
        }
        # Configure the default mock for website verification
        self.mock_api_client.verify_website_with_ai.return_value = {
            "is_valid": True, "reasoning": "The website appears to be a valid business site."
        }

        # We will now use the REAL view_text_website tool, and patch `requests` within tests
        self.engine = ProcessingEngine(self.job_settings, self.mock_api_client, tools.view_text_website)

    def _create_test_record(self, name="Test Merchant", city="Testville"):
        """Helper to create a MerchantRecord with necessary string attributes."""
        return MerchantRecord(
            original_name=name,
            original_address="",
            original_city=city,
            original_country="USA",
            original_state="",
            cleaned_merchant_name=name # Start with a default cleaned name
        )

    @patch('src.tools.requests.get')
    def test_successful_website_found(self, mock_requests_get):
        """Test a successful workflow where the AI finds a valid website."""
        # Arrange
        mock_response = MagicMock()
        mock_response.text = "<html><body>Official Business Content</body></html>"
        mock_response.headers = {'content-type': 'text/html'}
        mock_response.raise_for_status.return_value = None
        mock_requests_get.return_value = mock_response

        self.mock_api_client.search_web.return_value = [{"title": "Official Site", "link": "http://example.com"}]
        self.mock_api_client.analyze_search_results.return_value = {
            "cleaned_merchant_name": "Example Corp",
            "website_candidates": ["http://example.com"],
            "social_media_candidates": [],
            "business_status": "Operational",
            "extraction_summary": "Found official website."
        }
        record = self._create_test_record(name="EXAMPLE")

        # Act
        result = self.engine.process_record(record)

        # Assert
        self.assertEqual(result.cleaned_merchant_name, "Example Corp")
        self.assertEqual(result.website, "http://example.com")
        self.assertEqual(result.socials, [])
        self.assertEqual(result.remarks, "")
        self.assertEqual(result.logo_filename, "example.png")
        self.assertIn("SUCCESS: Website 'http://example.com' verified", result.evidence)
        self.mock_api_client.verify_website_with_ai.assert_called_once()

    @patch('src.tools.requests.get')
    def test_successful_socials_found(self, mock_requests_get):
        """Test a successful workflow where only social media is found after all searches."""
        # Arrange
        mock_response = MagicMock()
        mock_response.text = "<html><body>Some other content</body></html>"
        mock_response.headers = {'content-type': 'text/html'}
        mock_requests_get.return_value = mock_response

        self.mock_api_client.search_web.return_value = [{"title": "Facebook Page", "link": "http://facebook.com/example"}]
        self.mock_api_client.analyze_search_results.return_value = {
            "cleaned_merchant_name": "Example Corp",
            "website_candidates": [], # No websites found
            "social_media_candidates": ["http://facebook.com/example"],
            "business_status": "Operational",
            "extraction_summary": "Found official social media."
        }
        # Make website verification fail for this test
        self.mock_api_client.verify_website_with_ai.return_value = {"is_valid": False, "reasoning": "Not a valid site."}

        record = self._create_test_record(name="EXAMPLE")

        # Act
        result = self.engine.process_record(record)

        # Assert
        self.assertEqual(result.cleaned_merchant_name, "Example Corp")
        self.assertEqual(result.website, "")
        self.assertEqual(result.socials, ["http://facebook.com/example"])
        self.assertEqual(result.remarks, "website unavailable")
        self.assertEqual(result.logo_filename, "ExampleCorp.png")
        self.assertIn("Falling back to best social media link", result.evidence)

    @patch('src.tools.requests.get')
    def test_business_permanently_closed(self, mock_requests_get):
        """Test that a business marked 'Permanently Closed' is rejected."""
        # Arrange
        self.mock_api_client.search_web.return_value = [{"title": "Some business", "link": "http://other.com"}]
        self.mock_api_client.analyze_search_results.return_value = {
            "cleaned_merchant_name": "Old Business Inc",
            "website_candidates": ["http://other.com"],
            "social_media_candidates": [],
            "business_status": "Permanently Closed", # Key for this test
            "extraction_summary": "Business is permanently closed."
        }
        record = self._create_test_record(name="Old Business Inc")

        # Act
        result = self.engine.process_record(record)

        # Assert
        self.assertEqual(result.cleaned_merchant_name, "")
        self.assertEqual(result.website, "")
        self.assertEqual(result.remarks, "NA")
        self.assertIn("Rejected due to business status", result.evidence)

    def test_no_match_found(self):
        """Test the case where no usable information is found."""
        # Arrange
        self.mock_api_client.search_web.return_value = [] # No search results
        self.mock_api_client.analyze_search_results.return_value = None # AI analysis fails
        record = self._create_test_record(name="OBSCURE BIZ")

        # Act
        result = self.engine.process_record(record)

        # Assert
        self.assertEqual(result.cleaned_merchant_name, "")
        self.assertEqual(result.remarks, "NA")
        self.assertIn("No valid business match found", result.evidence)

    @patch('src.tools.requests.get')
    def test_website_overrides_socials_rule(self, mock_requests_get):
        """
        Test that finding a website correctly clears the social media links,
        even if the AI analysis provided both.
        """
        # Arrange: AI analysis returns both a website and social links
        mock_response = MagicMock()
        mock_response.text = "<html><body>Official Business Content</body></html>"
        mock_response.headers = {'content-type': 'text/html'}
        mock_requests_get.return_value = mock_response

        self.mock_api_client.search_web.return_value = [{"title": "Official Site", "link": "http://example.com"}]
        self.mock_api_client.analyze_search_results.return_value = {
            "cleaned_merchant_name": "Example Corp",
            "website_candidates": ["http://example.com"],
            "social_media_candidates": ["http://facebook.com/example"], # AI found this
            "business_status": "Operational",
            "extraction_summary": "Found official website and a social page."
        }
        record = self._create_test_record(name="EXAMPLE")

        # Act
        result = self.engine.process_record(record)

        # Assert: The business rule should prioritize the website and clear socials.
        self.assertEqual(result.website, "http://example.com")
        self.assertEqual(result.socials, [], "Socials should be empty if a website is found.")
        self.assertEqual(result.remarks, "", "Remarks should be empty on successful website match.")

    def test_logo_filename_generation_logic(self):
        """Test the logo filename generation logic for website and social cases."""
        # Test website case
        record_web = self._create_test_record()
        record_web.website = "http://www.web-inc.co.uk"
        filename_web = self.engine._generate_logo_filename(record_web)
        self.assertEqual(filename_web, "web-inc.png")

        # Test social media case
        record_social = self._create_test_record()
        record_social.cleaned_merchant_name = "Social Company"
        record_social.socials = ["http://facebook.com/social"]
        filename_social = self.engine._generate_logo_filename(record_social)
        self.assertEqual(filename_social, "SocialCompany.png") # Changed to match case-preserving logic

        # Test no website or social case
        record_none = self._create_test_record()
        filename_none = self.engine._generate_logo_filename(record_none)
        self.assertEqual(filename_none, "")

    @patch('src.tools.requests.get')
    def test_engine_with_successful_website_fetch(self, mock_requests_get):
        """Test the engine correctly uses the real website fetch tool on success."""
        # Arrange
        mock_response = MagicMock()
        mock_response.text = "<html><body>Real Fetched Content</body></html>"
        mock_response.headers = {'content-type': 'text/html'}
        mock_response.raise_for_status.return_value = None
        mock_requests_get.return_value = mock_response

        self.mock_api_client.analyze_search_results.return_value = {
            "website_candidates": ["http://real-site.com"],
            "cleaned_merchant_name": "Real Site",
            "social_media_candidates": [], "business_status": "Operational", "extraction_summary": ""
        }
        record = self._create_test_record(name="Real Site")

        # Act
        self.engine.process_record(record)

        # Assert
        mock_requests_get.assert_called_once_with("http://real-site.com", timeout=10, headers=unittest.mock.ANY)
        self.mock_api_client.verify_website_with_ai.assert_called_once_with(
            "<html><body>Real Fetched Content</body></html>", "Real Site"
        )

    @patch('src.tools.requests.get', side_effect=requests.exceptions.ConnectionError("Failed to connect"))
    def test_engine_with_failed_website_fetch(self, mock_requests_get):
        """Test the engine gracefully handles a website fetch failure and falls back to social."""
        # Arrange
        # First analysis finds a failing website. Subsequent analyses find only socials.
        analysis_with_failing_site = {
            "website_candidates": ["http://failing-site.com"],
            "cleaned_merchant_name": "Failing Site",
            "social_media_candidates": ["http://facebook.com/fallback"],
            "business_status": "Operational", "extraction_summary": "Found a failing site."
        }
        analysis_with_social_only = {
            "website_candidates": [],
            "cleaned_merchant_name": "Failing Site",
            "social_media_candidates": ["http://facebook.com/fallback"],
            "business_status": "Operational", "extraction_summary": "Found only a social link."
        }
        self.mock_api_client.analyze_search_results.side_effect = [
            analysis_with_failing_site,
            analysis_with_social_only,
            analysis_with_social_only,
            analysis_with_social_only,
            analysis_with_social_only,
            analysis_with_social_only
        ]
        # Make search_web return something every time so analyze is called.
        self.mock_api_client.search_web.return_value = [{"title": "Some result"}]

        record = self._create_test_record(name="Failing Site")

        # Act
        result = self.engine.process_record(record)

        # Assert
        # With the new retry logic, the failed fetch will be attempted 3 times (1 initial + 2 retries)
        self.assertEqual(mock_requests_get.call_count, 3, "The failing request should be retried.")
        self.assertEqual(result.website, "", "Website should be blank after fetch failure")
        self.assertIn("http://facebook.com/fallback", result.socials, "Should have fallen back to social media")
        self.assertIn("Website 'http://failing-site.com' rejected.", result.evidence, "Evidence should show rejection")
        self.assertIn("Failed to connect", result.evidence, "Evidence should show the connection error")


if __name__ == '__main__':
    unittest.main()