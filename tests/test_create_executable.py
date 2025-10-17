import unittest
from unittest.mock import patch, MagicMock
import sys

# Add the root directory to the Python path to allow importing 'create_executable'
sys.path.append(sys.path[0] + "/..")
import create_executable

class TestCreateExecutable(unittest.TestCase):

    @patch('create_executable.messagebox')
    @patch('create_executable.filedialog')
    def test_get_icon_path_user_selects_icon(self, mock_filedialog, mock_messagebox):
        """Test that get_icon_path returns the selected path when the user provides one."""
        # Arrange: User says "yes" to adding an icon
        mock_messagebox.askyesno.return_value = True
        # User selects a file
        mock_filedialog.askopenfilename.return_value = "/path/to/my_icon.ico"

        # Act
        result = create_executable.get_icon_path()

        # Assert
        self.assertEqual(result, "/path/to/my_icon.ico")
        mock_messagebox.showwarning.assert_not_called()

    @patch('create_executable.messagebox')
    @patch('create_executable.filedialog')
    def test_get_icon_path_user_cancels_dialog(self, mock_filedialog, mock_messagebox):
        """Test that get_icon_path returns None and warns if the user cancels the file dialog."""
        # Arrange: User says "yes" to adding an icon
        mock_messagebox.askyesno.return_value = True
        # User cancels the file selection
        mock_filedialog.askopenfilename.return_value = ""

        # Act
        result = create_executable.get_icon_path()

        # Assert
        self.assertIsNone(result)
        mock_messagebox.showwarning.assert_called_once()

    @patch('create_executable.messagebox')
    def test_get_icon_path_user_says_no(self, mock_messagebox):
        """Test that get_icon_path returns None if the user says "no" to adding an icon."""
        # Arrange: User says "no" to adding an icon
        mock_messagebox.askyesno.return_value = False

        # Act
        result = create_executable.get_icon_path()

        # Assert
        self.assertIsNone(result)

    @patch('os.path.exists', return_value=True)
    @patch('subprocess.Popen')
    def test_create_executable_with_icon(self, mock_popen, mock_exists):
        """Verify that the --icon argument is correctly added to the command."""
        # Arrange
        mock_process = MagicMock()
        mock_process.poll.return_value = 0 # Simulate process finishing
        mock_popen.return_value = mock_process
        icon_path = "C:/icons/app.ico"

        # Act
        create_executable.create_executable(icon_path=icon_path)

        # Assert
        mock_popen.assert_called_once()
        args, kwargs = mock_popen.call_args
        command_list = args[0]
        self.assertIn("--icon", command_list)
        # Find the index of --icon and check the next element
        icon_arg_index = command_list.index("--icon")
        self.assertEqual(command_list[icon_arg_index + 1], icon_path)

    @patch('os.path.exists', return_value=True)
    @patch('subprocess.Popen')
    def test_create_executable_without_icon(self, mock_popen, mock_exists):
        """Verify that the --icon argument is not added if no path is provided."""
        # Arrange
        mock_process = MagicMock()
        mock_process.poll.return_value = 0 # Simulate process finishing
        mock_popen.return_value = mock_process

        # Act
        create_executable.create_executable(icon_path=None)

        # Assert
        mock_popen.assert_called_once()
        args, kwargs = mock_popen.call_args
        command_list = args[0]
        self.assertNotIn("--icon", command_list)

if __name__ == '__main__':
    unittest.main()