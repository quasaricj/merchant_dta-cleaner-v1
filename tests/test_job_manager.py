import unittest
from unittest.mock import patch, Mock, ANY
import os
import pandas as pd
import time
import json

from src.core.job_manager import JobManager
from src.core.data_model import JobSettings, ApiConfig, ColumnMapping, MerchantRecord

DUMMY_PROCESSED_RECORD = MerchantRecord(original_name="Test", cleaned_merchant_name="Test Cleaned")

class TestJobManager(unittest.TestCase):

    def setUp(self):
        """Set up a test environment before each test."""
        self.test_input_file = "test_input.xlsx"
        self.test_output_file = "test_output_cleaned.xlsx"
        self.checkpoint_file = f"{self.test_input_file}.checkpoint.json"

        self.dummy_df = pd.DataFrame({"Merchant Name": [f"Merchant {i}" for i in range(10)], "Country": ["USA"] * 10})
        self.dummy_df.to_excel(self.test_input_file, index=False)

        self.api_config = ApiConfig("fake_gemini", "fake_search", "fake_cse")
        self.column_mapping = ColumnMapping(merchant_name="Merchant Name", country="Country")
        self.job_settings = JobSettings(
            input_filepath=self.test_input_file,
            output_filepath=self.test_output_file,
            column_mapping=self.column_mapping,
            start_row=2,
            end_row=12, # Process all 10 rows of data (2-11)
            mode="Basic",
            model_name="models/gemini-test"
        )
        self.status_callback = Mock()
        self.completion_callback = Mock()

    def tearDown(self):
        """Clean up files created during tests."""
        for f in [self.test_input_file, self.test_output_file, self.checkpoint_file, "job.log"]:
            if os.path.exists(f):
                os.remove(f)

    @patch('src.core.job_manager.GoogleApiClient')
    @patch('src.core.job_manager.ProcessingEngine')
    def test_full_successful_run(self, MockProcessingEngine, MockGoogleApiClient):
        """Test a complete, successful job run from start to finish."""
        mock_engine_instance = Mock()
        mock_engine_instance.process_record.return_value = DUMMY_PROCESSED_RECORD
        MockProcessingEngine.return_value = mock_engine_instance

        manager = JobManager(self.job_settings, self.api_config, self.status_callback, self.completion_callback)
        manager.start()
        manager._thread.join(timeout=5)

        self.assertEqual(mock_engine_instance.process_record.call_count, 10)
        self.status_callback.assert_called_with(10, 10, "Processing...")
        self.completion_callback.assert_called_once_with("Job Completed Successfully")
        self.assertTrue(os.path.exists(self.test_output_file))
        self.assertFalse(os.path.exists(self.checkpoint_file))

    @patch('src.core.job_manager.GoogleApiClient')
    @patch('src.core.job_manager.ProcessingEngine')
    def test_processes_correct_row_range(self, MockProcessingEngine, MockGoogleApiClient):
        """Test that the job manager processes only the specified row range."""
        mock_engine_instance = Mock()
        mock_engine_instance.process_record.return_value = DUMMY_PROCESSED_RECORD
        MockProcessingEngine.return_value = mock_engine_instance
        self.job_settings.start_row = 4
        self.job_settings.end_row = 8 # Process rows 4, 5, 6, 7, 8 (5 rows total)

        manager = JobManager(self.job_settings, self.api_config, self.status_callback, self.completion_callback)
        manager.start()
        manager._thread.join(timeout=5)

        self.assertEqual(mock_engine_instance.process_record.call_count, 5)
        self.status_callback.assert_called_with(5, 5, "Processing...")
        self.completion_callback.assert_called_once_with("Job Completed Successfully")

    @patch('src.core.job_manager.GoogleApiClient')
    @patch('src.core.job_manager.ProcessingEngine')
    def test_stop_workflow(self, MockProcessingEngine, MockGoogleApiClient):
        """Test that stopping a job saves a partial output file."""
        mock_engine_instance = Mock()
        mock_engine_instance.process_record.side_effect = lambda r: time.sleep(0.05) or DUMMY_PROCESSED_RECORD
        MockProcessingEngine.return_value = mock_engine_instance

        manager = JobManager(self.job_settings, self.api_config, self.status_callback, self.completion_callback)
        manager.start()
        time.sleep(0.1)
        manager.stop()
        manager._thread.join(timeout=5)

        self.completion_callback.assert_called_once_with("Job Stopped")
        self.assertLess(mock_engine_instance.process_record.call_count, 10)
        self.assertGreater(mock_engine_instance.process_record.call_count, 0)
        self.assertTrue(os.path.exists(self.test_output_file))

    @patch('src.core.job_manager.GoogleApiClient')
    @patch('src.core.job_manager.ProcessingEngine')
    @patch('pandas.DataFrame.to_excel', side_effect=PermissionError("Test permission denied"))
    def test_file_write_error_handling(self, mock_to_excel, MockProcessingEngine, MockGoogleApiClient):
        """Test that a file write error is caught, reported, and the checkpoint is saved."""
        mock_engine_instance = Mock()
        mock_engine_instance.process_record.return_value = DUMMY_PROCESSED_RECORD
        MockProcessingEngine.return_value = mock_engine_instance

        manager = JobManager(self.job_settings, self.api_config, self.status_callback, self.completion_callback)
        manager.start()
        manager._thread.join(timeout=5)

        self.completion_callback.assert_called_once()
        args, _ = self.completion_callback.call_args
        self.assertIn("Job Failed", args[0])
        self.assertIn("Could not write to output file", args[0])
        self.assertTrue(os.path.exists(self.checkpoint_file))

    @patch('src.core.job_manager.GoogleApiClient')
    @patch('src.core.job_manager.ProcessingEngine')
    def test_model_name_is_passed_to_api_client(self, MockProcessingEngine, MockGoogleApiClient):
        """Verify that the selected model_name is passed to the GoogleApiClient."""
        self.job_settings.model_name = "models/gemini-test-model"
        mock_engine_instance = Mock()
        mock_engine_instance.process_record.return_value = DUMMY_PROCESSED_RECORD
        MockProcessingEngine.return_value = mock_engine_instance

        manager = JobManager(self.job_settings, self.api_config, self.status_callback, self.completion_callback)
        manager.start()
        manager._thread.join(timeout=5)

        MockGoogleApiClient.assert_called_once_with(self.api_config, model_name="models/gemini-test-model")

if __name__ == '__main__':
    unittest.main()