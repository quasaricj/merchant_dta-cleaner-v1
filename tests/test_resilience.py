"""
This module contains tests for the application's resilience features, such as
API retries, pre-flight validation, and graceful error handling.
"""
import unittest
import time
import os
import tempfile
import shutil
from unittest.mock import MagicMock, patch

# It's important to import the MOCK version for testing
from src.services.mock_google_api_client import MockGoogleApiClient, MockHttpError429, MockHttpError503, MockQuotaExceededError
from src.core.job_manager import JobManager
from src.core.data_model import JobSettings, ApiConfig, ColumnMapping
from src.core.processing_engine import ProcessingEngine


class TestResilience(unittest.TestCase):
    """Test suite for application resilience."""

    def setUp(self):
        """Set up common resources for each test."""
        self.test_dir = tempfile.mkdtemp()
        self.test_input_file = os.path.join(self.test_dir, "test_input.xlsx")
        self.test_output_file = os.path.join(self.test_dir, "test_output.xlsx")
        # Create a dummy input file
        with open(self.test_input_file, "w", encoding="utf-8") as f:
            f.write("test")

        self.api_config = ApiConfig(gemini_api_key="fake-gemini-key", search_api_key="fake-search-key", search_cse_id="fake-cse-id")
        self.mock_api_client = MockGoogleApiClient(self.api_config)

        # Mock settings for JobManager and ProcessingEngine
        self.settings = JobSettings(
            input_filepath=self.test_input_file,
            output_filepath=self.test_output_file,
            start_row=2,
            end_row=3,
            mode="Basic",
            model_name="models/gemini-1.5-flash-latest",
            column_mapping=ColumnMapping(merchant_name="Merchant Name"),
            output_columns=[]
        )

        # Mock callbacks for JobManager
        self.status_callback = MagicMock()
        self.completion_callback = MagicMock()
        self.logo_status_callback = MagicMock()
        self.logo_completion_callback = MagicMock()
        self.view_text_website_func = MagicMock(return_value="<html></html>")

    def tearDown(self):
        """Clean up the temporary directory."""
        shutil.rmtree(self.test_dir)

    def test_retry_on_rate_limit_error(self):
        """
        Test Case 1: Rate Limiting.
        Verify that the retry decorator correctly handles a 429 error.
        """
        # Configure the mock client to fail the first time, then succeed
        call_count = 0
        original_search = self.mock_api_client.search_web

        def failing_then_succeeding_search(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise MockHttpError429("Simulated rate limit")
            return original_search(*args, **kwargs)

        self.mock_api_client.search_web = MagicMock(side_effect=failing_then_succeeding_search)
        self.mock_api_client.search_web.__name__ = "search_web" # Set name for decorator logging

        # We need to test the real GoogleApiClient's decorator, but we can do it
        # by patching the actual call inside it to use our mock behavior.
        # A simpler way for this test is to directly test the decorated function in isolation.
        # Let's test the retry logic on the ProcessingEngine level.
        engine = ProcessingEngine(self.settings, self.mock_api_client, self.view_text_website_func)

        # This should succeed after one retry
        from src.services.api_util import retry_with_backoff

        # We decorate the mock method to test the decorator itself
        decorated_search = retry_with_backoff(retries=2, initial_delay=0.1)(self.mock_api_client.search_web)

        # Execute
        start_time = time.time()
        result = decorated_search("test query")
        end_time = time.time()

        # Assert
        self.assertIsNotNone(result) # It should have succeeded eventually
        self.assertEqual(call_count, 2) # It was called twice (1 fail, 1 success)
        self.assertGreater(end_time - start_time, 0.1) # It should have delayed

    def test_retry_on_service_unavailable(self):
        """
        Test Case 2: Service Failure.
        Verify that the retry decorator handles a 503 error.
        """
        # Configure the mock client to fail twice, then succeed
        call_count = 0
        original_search = self.mock_api_client.search_web

        def failing_twice_then_succeeding(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise MockHttpError503("Simulated service unavailable")
            return original_search(*args, **kwargs)

        self.mock_api_client.search_web = MagicMock(side_effect=failing_twice_then_succeeding)
        self.mock_api_client.search_web.__name__ = "search_web"
        from src.services.api_util import retry_with_backoff
        decorated_search = retry_with_backoff(retries=3, initial_delay=0.1)(self.mock_api_client.search_web)

        # Execute
        start_time = time.time()
        result = decorated_search("test query")
        end_time = time.time()

        # Assert
        self.assertIsNotNone(result)
        self.assertEqual(call_count, 3) # Called three times (2 fail, 1 success)
        # Total delay should be 0.1 + (0.1 * 2) = 0.3
        self.assertGreater(end_time - start_time, 0.3)

    @patch('src.core.job_manager.GoogleApiClient', new=MockGoogleApiClient)
    def test_preflight_check_invalid_api_key(self):
        """
        Test Case 3: Pre-flight Checks (API Key).
        Verify JobManager.start() fails with an invalid API key.
        """
        job_manager = JobManager(self.settings, self.api_config, self.status_callback, self.completion_callback, self.logo_status_callback, self.logo_completion_callback, self.view_text_website_func)

        # Force the mock client to simulate an invalid key
        # We access the *class* and set the flag on the instance it will create
        with patch.object(MockGoogleApiClient, 'validate_api_keys', side_effect=ConnectionError("Invalid Key")):
             with self.assertRaisesRegex(ConnectionError, "API key validation failed"):
                job_manager.start()

    @patch('src.core.job_manager.os.path.exists', return_value=True) # Mock file existence
    @patch('src.core.job_manager.os.remove')
    @patch('builtins.open')
    @patch('src.core.job_manager.GoogleApiClient')
    def test_preflight_check_no_write_permission(self, mock_api_client, mock_open, mock_remove, mock_exists):
        """
        Test Case 3: Pre-flight Checks (Write Permission).
        Verify JobManager.start() fails when the output directory is not writable.
        """
        # Simulate a permission error when trying to write the test file
        mock_open.side_effect = PermissionError("Permission denied")

        job_manager = JobManager(self.settings, self.api_config, self.status_callback, self.completion_callback, self.logo_status_callback, self.logo_completion_callback, self.view_text_website_func)

        with self.assertRaisesRegex(PermissionError, "Cannot write to output directory"):
            job_manager.start()

    def test_job_stops_on_search_quota_exceeded(self):
        """
        Test Case 4: Search Quota.
        Verify the job stops gracefully when the search quota is exhausted.
        """
        # Configure the mock to throw a quota error on the first search call
        self.mock_api_client.search_web = MagicMock(side_effect=MockQuotaExceededError("Daily limit reached"))
        from src.services.api_util import retry_with_backoff
        decorated_search = retry_with_backoff()(self.mock_api_client.search_web)

        # The decorator should not retry quota errors, it should re-raise immediately
        self.mock_api_client.search_web.__name__ = "search_web"
        with self.assertRaises(MockQuotaExceededError):
            decorated_search("any query")

        # Check that it was only called once
        self.assertEqual(self.mock_api_client.search_web.call_count, 1)


if __name__ == '__main__':
    unittest.main()