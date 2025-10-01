import unittest
from src.core.data_model import MerchantRecord, ApiConfig, ColumnMapping, JobSettings

class TestDataModels(unittest.TestCase):

    def test_merchant_record_defaults(self):
        """Test that a MerchantRecord initializes with correct default values."""
        record = MerchantRecord(original_name="Test Merchant")

        self.assertEqual(record.original_name, "Test Merchant")
        self.assertIsNone(record.original_address)
        self.assertEqual(record.cleaned_merchant_name, "")
        self.assertEqual(record.website, "")
        self.assertEqual(record.socials, [])
        self.assertEqual(record.evidence, "")
        self.assertEqual(record.evidence_links, [])
        self.assertEqual(record.cost_per_row, 0.0)
        self.assertEqual(record.remarks, "")
        self.assertEqual(record.other_data, {})

    def test_merchant_record_with_data(self):
        """Test that a MerchantRecord can be created with all fields populated."""
        record = MerchantRecord(
            original_name="Original",
            original_address="123 Street",
            cleaned_merchant_name="Cleaned",
            website="http://example.com",
            socials=["http://facebook.com/example"],
            evidence="Found on web",
            cost_per_row=0.05,
            other_data={"extra_col": "extra_val"}
        )
        self.assertEqual(record.cleaned_merchant_name, "Cleaned")
        self.assertEqual(record.cost_per_row, 0.05)
        self.assertEqual(record.other_data["extra_col"], "extra_val")
        self.assertEqual(len(record.socials), 1)

    def test_job_settings_creation(self):
        """Test the creation of a JobSettings object."""
        mapping = ColumnMapping(merchant_name="Name")
        settings = JobSettings(
            input_filepath="in.xlsx",
            output_filepath="out.xlsx",
            column_mapping=mapping,
            start_row=5,
            end_row=100,
            mode="Enhanced"
        )
        self.assertEqual(settings.start_row, 5)
        self.assertEqual(settings.mode, "Enhanced")
        self.assertEqual(settings.column_mapping.merchant_name, "Name")

if __name__ == '__main__':
    unittest.main()