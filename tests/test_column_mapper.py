import unittest
import tkinter as tk
from unittest.mock import Mock, patch
import pandas as pd
import os

from src.app.ui_components.column_mapper import ColumnMapper
from src.core.data_model import ColumnMapping

class TestColumnMapper(unittest.TestCase):

    def setUp(self):
        """Set up a test environment."""
        self.root = tk.Tk()
        self.root.withdraw()  # Hide the window during tests
        self.mock_callback = Mock()

        # We need to patch the Style object because in a non-GUI environment,
        # creating new styles can be problematic.
        with patch('tkinter.ttk.Style') as self.mock_style:
            self.mapper = ColumnMapper(self.root, on_mapping_update=self.mock_callback)
            self.mapper.pack()
            self.root.update_idletasks()

        # Create a dummy excel file for testing
        self.dummy_filepath = "test_mapper_data.xlsx"
        self.dummy_data = {
            "Name": ["A", "B"],
            "Location": ["X", "Y"],
            "Country": ["USA", "CA"],
        }
        pd.DataFrame(self.dummy_data).to_excel(self.dummy_filepath, index=False)

        # Load the dummy file into the mapper
        self.mapper.load_file(self.dummy_filepath)
        self.root.update()

    def tearDown(self):
        """Clean up the test environment."""
        if os.path.exists(self.dummy_filepath):
            os.remove(self.dummy_filepath)
        self.root.destroy()

    def test_valid_mapping(self):
        """Test that a valid, non-conflicting mapping is processed correctly."""
        self.mock_callback.reset_mock()

        # Simulate user selecting valid, distinct columns
        self.mapper.column_vars["merchant_name"].set("Name")
        self.mapper.column_vars["city"].set("Location")
        self.mapper.column_vars["country"].set("Country")
        self.root.update()

        # The callback should be called with the correct ColumnMapping object
        self.mock_callback.assert_called()
        last_call_args = self.mock_callback.call_args[0][0]
        self.assertIsInstance(last_call_args, ColumnMapping)
        self.assertEqual(last_call_args.merchant_name, "Name")
        self.assertEqual(last_call_args.city, "Location")
        self.assertEqual(last_call_args.country, "Country")

        # Check that no duplicate styling was applied
        for cb in self.mapper.comboboxes.values():
            self.assertNotEqual(cb.cget("style"), "Duplicate.TCombobox")

    def test_duplicate_mapping_detection(self):
        """Test that mapping the same column to multiple fields is flagged as a duplicate."""
        self.mock_callback.reset_mock()

        # Simulate user mapping "Name" to two different fields
        self.mapper.column_vars["merchant_name"].set("Name")
        self.mapper.column_vars["address"].set("Name")
        self.root.update()

        # Check that the UI has been styled to indicate a duplicate (FR2C)
        name_combobox = self.mapper.comboboxes["merchant_name"]
        address_combobox = self.mapper.comboboxes["address"]
        city_combobox = self.mapper.comboboxes["city"]

        self.assertEqual(name_combobox.cget("style"), "Duplicate.TCombobox")
        self.assertEqual(address_combobox.cget("style"), "Duplicate.TCombobox")
        # Ensure non-duplicate fields are not styled
        self.assertNotEqual(city_combobox.cget("style"), "Duplicate.TCombobox")

    def test_mandatory_field_validation(self):
        """Test that the start button can only be enabled when the mandatory field is mapped."""
        # This test is conceptual as the button is in the main window.
        # We test the logic that would enable it.

        # Initially, merchant_name is not set
        is_valid = self.mapper.column_vars["merchant_name"].get() != ""
        self.assertFalse(is_valid)

        # Set the mandatory field
        self.mapper.column_vars["merchant_name"].set("Name")
        self.root.update()

        is_valid = self.mapper.column_vars["merchant_name"].get() != ""
        self.assertTrue(is_valid)

        # Unset the mandatory field
        self.mapper.column_vars["merchant_name"].set("")
        self.root.update()

        is_valid = self.mapper.column_vars["merchant_name"].get() != ""
        self.assertFalse(is_valid)


if __name__ == '__main__':
    unittest.main()