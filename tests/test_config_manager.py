import unittest
import os
import json
import base64
from src.core.config_manager import (
    save_api_config,
    load_api_config,
    save_column_mapping,
    load_column_mapping,
    list_mapping_presets,
    CONFIG_FILE_PATH,
    MAPPING_PRESETS_DIR
)
from src.core.data_model import ApiConfig, ColumnMapping

class TestConfigManager(unittest.TestCase):

    def setUp(self):
        """Set up test environment."""
        self.test_api_config = ApiConfig(
            gemini_api_key="test_gemini_key",
            search_api_key="test_search_key",
            search_cse_id="test_cse_id",
            places_api_key="test_places_key"
        )
        self.test_column_mapping = ColumnMapping(
            merchant_name="Merchant Name Column",
            address="Address Column",
            city="City Column",
            country="Country Column",
            state="State Column"
        )
        # Ensure config directory exists
        if not os.path.exists('config'):
            os.makedirs('config')
        if not os.path.exists(MAPPING_PRESETS_DIR):
            os.makedirs(MAPPING_PRESETS_DIR)

    def tearDown(self):
        """Clean up after tests."""
        if os.path.exists(CONFIG_FILE_PATH):
            os.remove(CONFIG_FILE_PATH)
        for f in os.listdir(MAPPING_PRESETS_DIR):
            if f.endswith(".json"):
                os.remove(os.path.join(MAPPING_PRESETS_DIR, f))

    def test_save_and_load_api_config(self):
        """Test saving and loading a full API config."""
        save_api_config(self.test_api_config)
        self.assertTrue(os.path.exists(CONFIG_FILE_PATH))

        loaded_config = load_api_config()
        self.assertIsNotNone(loaded_config)
        self.assertEqual(loaded_config.gemini_api_key, self.test_api_config.gemini_api_key)
        self.assertEqual(loaded_config.search_api_key, self.test_api_config.search_api_key)
        self.assertEqual(loaded_config.search_cse_id, self.test_api_config.search_cse_id)
        self.assertEqual(loaded_config.places_api_key, self.test_api_config.places_api_key)

    def test_load_api_config_no_file(self):
        """Test loading API config when no file exists."""
        loaded_config = load_api_config()
        self.assertIsNone(loaded_config)

    def test_api_config_optional_places_key(self):
        """Test saving and loading API config with optional Places key."""
        config_no_places = ApiConfig(gemini_api_key="gemini",
                                     search_api_key="search",
                                     search_cse_id="cse")
        save_api_config(config_no_places)
        loaded_config = load_api_config()
        self.assertIsNotNone(loaded_config)
        self.assertEqual(loaded_config.gemini_api_key, "gemini")
        self.assertIsNone(loaded_config.places_api_key)

    def test_save_and_load_column_mapping(self):
        """Test saving and loading a column mapping preset."""
        preset_name = "test_preset"
        save_column_mapping(self.test_column_mapping, preset_name)

        preset_path = os.path.join(MAPPING_PRESETS_DIR, f"{preset_name}.json")
        self.assertTrue(os.path.exists(preset_path))

        loaded_mapping = load_column_mapping(preset_name)
        self.assertIsNotNone(loaded_mapping)
        self.assertEqual(loaded_mapping.merchant_name, self.test_column_mapping.merchant_name)
        self.assertEqual(loaded_mapping.address, self.test_column_mapping.address)

    def test_load_column_mapping_no_file(self):
        """Test loading a column mapping that doesn't exist."""
        loaded_mapping = load_column_mapping("non_existent_preset")
        self.assertIsNone(loaded_mapping)

    def test_list_mapping_presets(self):
        """Test listing available mapping presets."""
        self.assertEqual(list_mapping_presets(), [])

        save_column_mapping(self.test_column_mapping, "preset1")
        save_column_mapping(self.test_column_mapping, "preset2")

        presets = list_mapping_presets()
        self.assertEqual(len(presets), 2)
        self.assertIn("preset1", presets)
        self.assertIn("preset2", presets)

if __name__ == '__main__':
    unittest.main()