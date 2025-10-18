import unittest
import os
import shutil
import tempfile
import pandas as pd
from unittest.mock import MagicMock, patch

from src.core.logo_only_job_manager import LogoOnlyJobManager
from src.core.logo_scraper import LogoScraper

class TestLogoOnlyScraper(unittest.TestCase):

    def setUp(self):
        """Set up a temporary directory and create sample files."""
        self.test_dir = tempfile.mkdtemp()
        self.input_filepath = os.path.join(self.test_dir, "processed_input.xlsx")

        # Create a dummy fallback image
        self.fallback_image_path = os.path.join(self.test_dir, "fallback.png")
        with open(self.fallback_image_path, "wb") as f:
            f.write(b"dummyimagedata")

        # Create a dummy DataFrame with pre-filled data
        self.input_data = {
            'Cleaned Merchant': ['Google', 'Facebook', 'No Website Inc'],
            'Official Website': ['http://google.com', 'http://facebook.com', ''],
            'Social Links': ['', 'http://twitter.com/facebook', ''],
            'Logo Filename': ['google.png', 'facebook.png', 'nowebsite.png']
        }
        self.input_df = pd.DataFrame(self.input_data)
        self.input_df.to_excel(self.input_filepath, index=False)

        # Define the column mapping as it would come from the UI
        self.column_mapping = {
            "cleaned_merchant_name": "Cleaned Merchant",
            "website": "Official Website",
            "social_media_links": "Social Links",
            "logo_filename": "Logo Filename"
        }

    def tearDown(self):
        """Remove the temporary directory after the test."""
        shutil.rmtree(self.test_dir)

    @patch('src.core.logo_scraper.LogoScraper._find_logo_url')
    @patch('src.core.logo_scraper.LogoScraper._download_image')
    @patch('src.core.logo_only_job_manager.os.path.abspath')
    def test_logo_only_job_manager_workflow(self, mock_abspath, mock_download, mock_find_logo):
        """
        Verify the complete workflow of the LogoOnlyJobManager, from reading
        the file to creating the logo files and summary report.
        """
        # --- 1. Configure Mocks ---
        mock_abspath.return_value = self.fallback_image_path

        # Mock the download to actually create a dummy file
        def mock_download_side_effect(url, target_path):
            with open(target_path, "wb") as f:
                f.write(b"scraped_logo")
        mock_download.side_effect = mock_download_side_effect

        # Simulate finding a logo for Google, but not for Facebook
        def find_logo_side_effect(url):
            if "google.com" in url:
                return "http://google.com/logo.png"
            return None # Facebook and others will fail to find a logo

        mock_find_logo.side_effect = find_logo_side_effect

        # Mock callbacks
        status_callback = MagicMock()
        completion_callback = MagicMock()

        # --- 2. Initialize and run the job ---
        job_manager = LogoOnlyJobManager(
            input_filepath=self.input_filepath,
            column_mapping=self.column_mapping,
            status_callback=status_callback,
            completion_callback=completion_callback
        )
        # Run synchronously by calling the internal method
        job_manager._run()

        # --- 3. Verify the results ---
        # Check that the completion callback was called with a success message
        completion_callback.assert_called_once()
        final_status = completion_callback.call_args[0][0]
        self.assertIn("Logo scraping complete. See folder:", final_status)

        # Extract the output directory from the final status
        output_dir = final_status.split("See folder:")[1].strip()
        self.assertTrue(os.path.isdir(output_dir))

        # Check the created files
        created_files = os.listdir(output_dir)

        # We expect 3 logo files (1 scraped, 2 fallbacks) and 1 report file
        self.assertEqual(len(created_files), 4)
        self.assertIn("google.png", created_files)
        self.assertIn("facebook.png", created_files)
        self.assertIn("nowebsite.png", created_files)
        self.assertIn("scraping_report.csv", created_files)

        # Verify the _find_logo_url was called for the two records with websites
        self.assertEqual(mock_find_logo.call_count, 2)
        mock_find_logo.assert_any_call('http://google.com')
        mock_find_logo.assert_any_call('http://facebook.com')

        # Verify that _download_image was only called for Google (the one that was found)
        mock_download.assert_called_once_with("http://google.com/logo.png", os.path.join(output_dir, 'google.png'))

if __name__ == '__main__':
    unittest.main()