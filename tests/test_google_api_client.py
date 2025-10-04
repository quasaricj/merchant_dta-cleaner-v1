import unittest
from unittest.mock import patch, MagicMock
from src.services.google_api_client import GoogleApiClient
from google.api_core import exceptions as google_exceptions

class TestGoogleApiClient(unittest.TestCase):

    @patch('google.generativeai.configure')
    @patch('google.generativeai.list_models')
    def test_validate_and_list_models_success(self, mock_list_models, mock_configure):
        """Test successful API key validation and model filtering."""
        # Mock the return value of genai.list_models()
        mock_model_flash = MagicMock()
        mock_model_flash.name = "models/gemini-1.5-flash-latest"
        mock_model_flash.supported_generation_methods = ['generateContent']

        mock_model_pro = MagicMock()
        mock_model_pro.name = "models/gemini-1.5-pro-latest"
        mock_model_pro.supported_generation_methods = ['generateContent']

        mock_model_unsupported = MagicMock()
        mock_model_unsupported.name = "models/embedding-001"
        mock_model_unsupported.supported_generation_methods = ['embedContent']

        mock_list_models.return_value = [mock_model_flash, mock_model_pro, mock_model_unsupported]

        api_key = "valid_api_key"
        models = GoogleApiClient.validate_and_list_models(api_key)

        mock_configure.assert_called_once_with(api_key=api_key)
        self.assertIsNotNone(models)
        self.assertIn("models/gemini-1.5-flash-latest", models)
        self.assertNotIn("models/gemini-1.5-pro-latest", models) # Should be filtered out
        self.assertNotIn("models/embedding-001", models) # Should be filtered out

    @patch('google.generativeai.configure', side_effect=google_exceptions.PermissionDenied("Invalid API key"))
    def test_validate_and_list_models_permission_denied(self, mock_configure):
        """Test API validation failure due to an invalid key."""
        api_key = "invalid_api_key"
        models = GoogleApiClient.validate_and_list_models(api_key)
        self.assertIsNone(models)

    @patch('google.generativeai.configure')
    @patch('google.generativeai.list_models', side_effect=Exception("Unexpected error"))
    def test_validate_and_list_models_unexpected_error(self, mock_list_models, mock_configure):
        """Test handling of unexpected errors during model listing."""
        api_key = "valid_api_key"
        models = GoogleApiClient.validate_and_list_models(api_key)
        self.assertIsNone(models)

if __name__ == '__main__':
    unittest.main()