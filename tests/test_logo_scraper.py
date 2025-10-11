import unittest
import os
import shutil
from unittest.mock import patch, MagicMock

from src.core.logo_scraper import LogoScraper
from src.core.data_model import MerchantRecord

class TestLogoScraper(unittest.TestCase):
    def setUp(self):
        """Set up a temporary directory for test outputs."""
        self.output_dir = "test_logos_output"
        self.fallback_image_path = "data/image_for_logo_scraping_error.png" # Corrected path
        os.makedirs(self.output_dir, exist_ok=True)

        # Ensure the dummy fallback file exists for the test
        if not os.path.exists(self.fallback_image_path):
            os.makedirs(os.path.dirname(self.fallback_image_path), exist_ok=True)
            with open(self.fallback_image_path, "w", encoding="utf-8") as f:
                f.write("This is the official fallback logo image.")

    def tearDown(self):
        """Remove the temporary directory after tests."""
        shutil.rmtree(self.output_dir)

    @patch('src.core.logo_scraper.requests.get')
    def test_fallback_on_scraping_error(self, mock_requests_get):
        """
        Test that the scraper uses the fallback image when a request fails.
        """
        # Arrange
        # Simulate a network error during the download attempt
        mock_requests_get.side_effect = ConnectionError("Failed to connect")

        # Create a record that requires a logo
        record = MerchantRecord(
            original_name="Error Corp",
            cleaned_merchant_name="Error Corp",
            website="http://error-corp.com",
            logo_filename="ErrorCorp.png"
        )

        scraper = LogoScraper(
            records=[record],
            output_dir=self.output_dir,
            fallback_image_path=self.fallback_image_path
        )

        # Act
        scraper.run(progress_callback=lambda *args: None) # Run the scraper

        # Assert
        expected_logo_path = os.path.join(self.output_dir, "ErrorCorp.png")
        self.assertTrue(os.path.exists(expected_logo_path), "Fallback logo should have been created.")

        # Verify the content of the fallback file
        with open(expected_logo_path, 'r', encoding='utf-8') as f:
            content = f.read()
        self.assertEqual(content, "This is the official fallback logo image.") # Corrected content

        # Verify the report indicates a fallback was used
        self.assertIn("fallback used", scraper.report_data[0][1])

if __name__ == '__main__':
    unittest.main()