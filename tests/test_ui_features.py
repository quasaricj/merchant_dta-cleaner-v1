import unittest
from unittest.mock import patch, MagicMock
import os
import sys
import tkinter as tk

# Add src to path to allow imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.app.main_window import MainWindow

class TestUIFeatures(unittest.TestCase):

    @patch('tkinter.Tk')
    def setUp(self, mock_tk):
        # We patch Tk to prevent actual UI rendering during tests
        self.app = MainWindow()

    @patch('tkinter.Toplevel')
    @patch('src.app.main_window.mark_first_launch_complete')
    def test_show_user_guide(self, mock_mark_complete, mock_toplevel):
        """Test that the user guide window can be created."""
        with patch('builtins.open', unittest.mock.mock_open(read_data='# User Guide')) as mock_file:
            self.app.show_user_guide()
            mock_toplevel.assert_called_once()
            # Ensure we don't accidentally mark first launch as complete
            mock_mark_complete.assert_not_called()

    @patch('tkinter.Toplevel')
    @patch('src.app.main_window.mark_first_launch_complete')
    def test_show_user_guide_first_launch(self, mock_mark_complete, mock_toplevel):
        """Test that the user guide shows a welcome and marks first launch as complete."""
        with patch('builtins.open', unittest.mock.mock_open(read_data='# User Guide')) as mock_file:
            self.app.show_user_guide(is_first_launch=True)
            mock_toplevel.assert_called_once()
            mock_mark_complete.assert_called_once()

    @patch('tkinter.Toplevel')
    @patch('os.path.exists', return_value=True)
    @patch('subprocess.run')
    @patch('os.startfile')
    def test_logo_completion_dialog_shows_and_opens_folder(self, mock_startfile, mock_subprocess_run, mock_exists, mock_toplevel):
        """Test the logo completion dialog appears and the 'Open Folder' button works."""

        # This is a simplified way to test the Toplevel dialog's functionality
        # without fully rendering the UI. We'll check if the dialog is created
        # and if the correct folder-opening command is called.

        logo_path = "/fake/path/to/logos"
        status_message = f"Logo scraping complete. See folder: {logo_path}"

        # We need a way to "click" the button. We'll grab the command from the mock call.
        mock_button = MagicMock()

        # Mock the Toplevel and its children to find the button
        mock_dialog_instance = mock_toplevel.return_value

        with patch('tkinter.ttk.Button', return_value=mock_button):
            self.app._show_logo_completion_dialog(status_message, logo_path)

        mock_toplevel.assert_called_once()

        # Find the call to create the "Open Folder" button and extract the command
        open_folder_command = None
        for call in mock_button.call_args_list:
            if call.kwargs.get('text') == 'Open Folder':
                open_folder_command = call.kwargs.get('command')
                break

        self.assertIsNotNone(open_folder_command, "Open Folder button was not created.")

        # "Click" the button
        open_folder_command()

        # Check that the correct OS command was called
        if sys.platform == "win32":
            mock_startfile.assert_called_with(logo_path)
        elif sys.platform == "darwin":
            mock_subprocess_run.assert_called_with(["open", logo_path], check=True)
        else:
            mock_subprocess_run.assert_called_with(["xdg-open", logo_path], check=True)

if __name__ == '__main__':
    unittest.main()