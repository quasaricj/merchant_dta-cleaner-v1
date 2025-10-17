import unittest
import os
import shutil
import tempfile
import pandas as pd
from unittest.mock import MagicMock, patch

from src.core.job_manager import JobManager
from src.core.data_model import JobSettings, ColumnMapping, ApiConfig, OutputColumnConfig

class TestRowRangeOutput(unittest.TestCase):

    def setUp(self):
        """Set up a temporary directory and create a sample Excel file."""
        self.test_dir = tempfile.mkdtemp()
        self.input_filepath = os.path.join(self.test_dir, "input.xlsx")
        self.output_filepath = os.path.join(self.test_dir, "output.xlsx")

        # Create a dummy DataFrame with 50 rows
        self.original_data = {
            'Merchant Name': [f'Merchant {i}' for i in range(1, 51)],
            'Some Data': [f'Data {i}' for i in range(1, 51)],
            'Process Status': ['Original'] * 50
        }
        self.original_df = pd.DataFrame(self.original_data)
        self.original_df.to_excel(self.input_filepath, index=False)

    def tearDown(self):
        """Remove the temporary directory after the test."""
        shutil.rmtree(self.test_dir)

    @patch('src.core.job_manager.ProcessingEngine')
    def test_output_file_preserves_unprocessed_rows(self, MockProcessingEngine):
        """
        Verify that processing a range of rows only updates those rows in the
        output file, preserving all other rows from the original file.
        """
        # --- 1. Configure Mocks and Settings ---
        mock_engine_instance = MockProcessingEngine.return_value
        def mock_process_record(record):
            record.remarks = "Processed"
            return record
        mock_engine_instance.process_record.side_effect = mock_process_record

        start_row = 11
        end_row = 25
        output_columns = [
            OutputColumnConfig(enabled=True, source_field='original_name', output_header='Merchant Name'),
            OutputColumnConfig(enabled=True, source_field='other_data.Some Data', output_header='Some Data'),
            OutputColumnConfig(enabled=True, source_field='remarks', output_header='Process Status')
        ]
        settings = JobSettings(
            input_filepath=self.input_filepath,
            output_filepath=self.output_filepath,
            column_mapping=ColumnMapping(merchant_name='Merchant Name'),
            output_columns=output_columns,
            start_row=start_row,
            end_row=end_row,
            mode="Basic",
            mock_mode=True,
            model_name="mock-model"
        )
        api_config = ApiConfig("dummy", "dummy", "dummy")
        status_callback, completion_callback, logo_status_callback, logo_completion_callback, view_text_website_func = (MagicMock() for _ in range(5))

        # --- 2. Run the Job ---
        job_manager = JobManager(
            settings, api_config, status_callback, completion_callback,
            logo_status_callback, logo_completion_callback, view_text_website_func
        )
        job_manager.start()
        job_manager._thread.join() # Wait for the thread to complete

        # --- 3. Verify the output file ---
        self.assertTrue(os.path.exists(self.output_filepath), "Output file was not created.")
        output_df = pd.read_excel(self.output_filepath)

        # Assert that the output file has the same number of rows as the input
        self.assertEqual(len(self.original_df), len(output_df))

        # Convert to dictionaries for easy comparison
        original_records = self.original_df.to_dict('records')
        output_records = output_df.to_dict('records')

        # Indices for the processed range (0-based)
        start_index = start_row - 2
        end_index = end_row - 1 # Inclusive index

        # Assert rows BEFORE the processed range are unchanged
        for i in range(0, start_index):
            self.assertDictEqual(original_records[i], output_records[i], f"Row {i+2} (before range) should be unchanged.")

        # Assert rows AFTER the processed range are unchanged
        for i in range(end_index, 50):
            # The processed data stops at end_index, so check from there onwards
            self.assertDictEqual(original_records[i], output_records[i], f"Row {i+2} (after range) should be unchanged.")

        # Assert rows WITHIN the processed range have been updated
        # The end_index for iloc is exclusive, so we loop up to end_index -1
        for i in range(start_index, end_index):
            self.assertEqual(output_records[i]['Merchant Name'], f'Merchant {i+1}')
            self.assertEqual(output_records[i]['Process Status'], 'Processed', f"Row {i+2} should be marked as 'Processed'.")

if __name__ == '__main__':
    unittest.main()