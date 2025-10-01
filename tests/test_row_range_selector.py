import unittest
import tkinter as tk
from unittest.mock import Mock

from src.app.ui_components.row_range_selector import RowRangeSelector

class TestRowRangeSelector(unittest.TestCase):

    def setUp(self):
        """Set up a test environment."""
        self.root = tk.Tk()
        # Hide the window during tests
        self.root.withdraw()
        self.mock_callback = Mock()
        self.selector = RowRangeSelector(self.root, on_range_update=self.mock_callback)
        self.selector.pack()
        self.root.update_idletasks()

    def tearDown(self):
        """Clean up the test environment."""
        self.root.destroy()

    def test_valid_range_selection(self):
        """Test that a valid range selection triggers the callback and updates the label."""
        self.selector.set_file_properties(total_rows=100) # This sets defaults (2 to 101) and calls the callback
        self.mock_callback.assert_called_with(2, 101)

        # Simulate user input
        self.selector.start_row_var.set("10")
        self.selector.end_row_var.set("50")
        self.root.update() # Triggers the variable traces

        # Check that the callback was called with the new, valid range
        self.mock_callback.assert_called_with(10, 50)
        # Check that the info label is correct and not showing an error
        self.assertIn("Selected: 41 rows", self.selector.info_label.cget("text"))
        self.assertNotEqual(self.selector.info_label.cget("foreground"), "red")

    def test_invalid_range_start_greater_than_end(self):
        """Test that an invalid range (start > end) is flagged and does not trigger the callback."""
        self.selector.set_file_properties(total_rows=100)
        self.mock_callback.reset_mock() # Reset after initial call from set_file_properties

        # Simulate invalid user input
        self.selector.start_row_var.set("50")
        self.selector.end_row_var.set("10")
        self.root.update()

        # Check that the info label shows an error
        self.assertIn("Invalid range", self.selector.info_label.cget("text"))
        self.assertEqual(str(self.selector.info_label.cget("foreground")), "red")
        # Check that the callback was only called for the valid intermediate step, not the final invalid one.
        self.mock_callback.assert_called_once_with(50, 101)

    def test_invalid_range_out_of_bounds(self):
        """Test that an out-of-bounds range is flagged as invalid."""
        self.selector.set_file_properties(total_rows=100)
        self.mock_callback.reset_mock()

        # Test end row > total rows
        self.selector.end_row_var.set("200")
        self.root.update()

        self.assertIn("Invalid range", self.selector.info_label.cget("text"))
        self.mock_callback.assert_not_called()

        # Test start row < 2
        self.selector.start_row_var.set("1")
        self.root.update()

        self.assertIn("Invalid range", self.selector.info_label.cget("text"))
        self.mock_callback.assert_not_called()

    def test_non_numeric_input(self):
        """Test that non-numeric input is flagged as invalid."""
        self.selector.set_file_properties(total_rows=100)
        self.mock_callback.reset_mock()

        # Simulate non-numeric input
        self.selector.start_row_var.set("abc")
        self.root.update()

        self.assertIn("Invalid number", self.selector.info_label.cget("text"))
        self.assertEqual(str(self.selector.info_label.cget("foreground")), "red")
        self.mock_callback.assert_not_called()

if __name__ == '__main__':
    unittest.main()