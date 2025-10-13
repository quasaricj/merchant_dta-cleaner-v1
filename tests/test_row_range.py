import unittest
import os
import shutil
import tempfile
import pandas as pd
from unittest.mock import patch

from src.core.job_manager import JobManager
from src.core.data_model import JobSettings, ColumnMapping, ApiConfig, MerchantRecord

class TestRowRange(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.input_path = os.path.join(self.test_dir, "input.xlsx")
        self.output_path = os.path.join(self.test_dir, "output.xlsx")

        data = {
            'Company': [f'Company {i}' for i in range(1, 21)],
            'Address': [f'{i} Street' for i in range(1, 21)]
        }
        df = pd.DataFrame(data)
        df.to_excel(self.input_path, index=False)

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    @patch('src.core.processing_engine.ProcessingEngine.process_record')
    def test_job_manager_processes_correct_row_range(self, mock_process_record):
        """
        Verify that the JobManager processes and writes only the user-specified row range.
        """
        def simple_process(record: MerchantRecord) -> MerchantRecord:
            record.cleaned_merchant_name = f"Processed {record.original_name}"
            record.website = "http://processed.com"
            return record
        mock_process_record.side_effect = simple_process

        settings = JobSettings(
            input_filepath=self.input_path,
            output_filepath=self.output_path,
            column_mapping=ColumnMapping(merchant_name="Company", address="Address"),
            start_row=5,
            end_row=10,
            mode="Basic",
            model_name="mock-model",
            mock_mode=True
        )
        api_config = ApiConfig()

        job_manager = JobManager(settings, api_config, lambda *args: None, lambda *args: None, lambda *args: None, lambda *args: None, lambda *args: "")

        with patch.object(job_manager, '_start_logo_scraping', return_value=None):
             job_manager._run(settings)

        self.assertTrue(os.path.exists(self.output_path))
        output_df = pd.read_excel(self.output_path)

        self.assertEqual(len(output_df), 6)
        self.assertEqual(output_df["Company"].iloc[0], "Company 4")
        self.assertEqual(output_df["Cleaned Merchant Name"].iloc[0], "Processed Company 4")
        self.assertEqual(output_df["Company"].iloc[-1], "Company 9")
        self.assertEqual(output_df["Cleaned Merchant Name"].iloc[-1], "Processed Company 9")

if __name__ == '__main__':
    unittest.main()