import unittest
import tkinter as tk
from unittest.mock import Mock, patch
from src.app.ui_components.output_column_configurator import OutputColumnConfigurator
from src.core.data_model import get_default_output_columns, OutputColumnConfig

class TestOutputColumnConfigurator(unittest.TestCase):

    def setUp(self):
        """Set up a root window and the configurator for testing."""
        try:
            self.root = tk.Tk()
            self.root.winfo_screen()
        except tk.TclError:
            self.root = None
            return
        self.mock_on_update = Mock()
        self.configurator = OutputColumnConfigurator(self.root, on_update=self.mock_on_update)

    def tearDown(self):
        """Destroy the root window after each test."""
        if self.root and self.root.winfo_exists():
            self.root.destroy()

    def test_initial_state(self):
        """Test that the configurator's content frame is empty initially."""
        if not self.root: self.skipTest("No UI available for this test.")
        self.assertEqual(len(self.configurator.scrollable_frame.winfo_children()), 0)

    def test_set_columns(self):
        """Test setting the columns and populating the UI."""
        if not self.root: self.skipTest("No UI available for this test.")
        default_columns = get_default_output_columns()
        self.configurator.set_columns(default_columns)
        self.assertEqual(len(self.configurator.columns), len(default_columns))
        # Header + Separator + number of column rows
        self.assertEqual(len(self.configurator.scrollable_frame.winfo_children()), 2 + len(default_columns))
        self.mock_on_update.assert_called_with(default_columns)

    def test_move_up(self):
        """Test moving a column up in the list."""
        if not self.root: self.skipTest("No UI available for this test.")
        columns = get_default_output_columns()
        self.configurator.set_columns(columns)

        item_to_move = self.configurator.columns[1]
        self.configurator._move_up(1)
        self.assertEqual(self.configurator.columns[0], item_to_move)

    def test_move_down(self):
        """Test moving a column down in the list."""
        if not self.root: self.skipTest("No UI available for this test.")
        columns = get_default_output_columns()
        self.configurator.set_columns(columns)

        item_to_move = self.configurator.columns[0]
        self.configurator._move_down(0)
        self.assertEqual(self.configurator.columns[1], item_to_move)

    @patch('tkinter.simpledialog.askstring', return_value="My Custom Column")
    @patch('tkinter.messagebox.showwarning')
    def test_add_and_remove_columns(self, mock_showwarning, mock_askstring):
        """Test adding a custom column and correctly handling removal logic."""
        if not self.root: self.skipTest("No UI available for this test.")
        columns = get_default_output_columns()
        self.configurator.set_columns(columns)
        initial_count = len(columns)

        # 1. Add a custom column
        self.configurator._add_column()
        self.assertEqual(len(self.configurator.columns), initial_count + 1)
        self.assertTrue(self.configurator.columns[-1].is_custom)

        # 2. Try to remove a standard column (should fail and show warning)
        self.configurator._remove_column(0)
        self.assertEqual(len(self.configurator.columns), initial_count + 1)
        mock_showwarning.assert_called_once()

        # 3. Remove the custom column (should succeed)
        self.configurator._remove_column(initial_count) # It's at the end
        self.assertEqual(len(self.configurator.columns), initial_count)

if __name__ == '__main__':
    unittest.main()