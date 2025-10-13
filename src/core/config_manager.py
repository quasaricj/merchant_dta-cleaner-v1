"""
Manages loading and saving of configuration files, such as API keys and
column mapping presets. All configurations are stored in the `config/` directory.
"""
import json
import base64
import os
from typing import Optional

from src.core.data_model import ApiConfig, ColumnMapping

CONFIG_FILE_PATH = "config/app_settings.json"
MAPPING_PRESETS_DIR = "config/mapping_presets"

def save_api_config(api_config: ApiConfig):
    """
    Saves the API configuration to the settings file, with simple base64 encoding.
    """
    if not os.path.exists("config"):
        os.makedirs("config")

    encoded_config = {
        "gemini_api_key": base64.b64encode(api_config.gemini_api_key.encode()).decode(),
        "search_api_key": base64.b64encode(api_config.search_api_key.encode()).decode(),
        "places_api_key": (
            base64.b64encode(api_config.places_api_key.encode()).decode()
            if api_config.places_api_key else None
        ),
    }

    with open(CONFIG_FILE_PATH, "w", encoding="utf-8") as f:
        json.dump({"api_keys": encoded_config}, f, indent=4)

def load_api_config() -> Optional[ApiConfig]:
    """
    Loads the API configuration from the settings file, decoding the keys.
    Returns None if the file doesn't exist or is invalid.
    """
    if not os.path.exists(CONFIG_FILE_PATH):
        return None

    try:
        with open(CONFIG_FILE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            encoded_config = data.get("api_keys", {})

            gemini_key = base64.b64decode(encoded_config.get("gemini_api_key", "")).decode()
            search_key = base64.b64decode(encoded_config.get("search_api_key", "")).decode()
            places_key_encoded = encoded_config.get("places_api_key")
            places_key = (
                base64.b64decode(places_key_encoded).decode() if places_key_encoded else None
            )

            return ApiConfig(
                gemini_api_key=gemini_key,
                search_api_key=search_key,
                places_api_key=places_key,
            )
    except (json.JSONDecodeError, FileNotFoundError, TypeError):
        return None

def save_column_mapping(mapping: ColumnMapping, preset_name: str):
    """
    Saves a column mapping configuration to a JSON file in the presets directory.
    """
    if not os.path.exists(MAPPING_PRESETS_DIR):
        os.makedirs(MAPPING_PRESETS_DIR)

    filepath = os.path.join(MAPPING_PRESETS_DIR, f"{preset_name}.json")
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(mapping.__dict__, f, indent=4)

def load_column_mapping(preset_name: str) -> Optional[ColumnMapping]:
    """
    Loads a column mapping configuration from a JSON file.
    """
    filepath = os.path.join(MAPPING_PRESETS_DIR, f"{preset_name}.json")
    if not os.path.exists(filepath):
        return None

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
            return ColumnMapping(**data)
    except (json.JSONDecodeError, FileNotFoundError, TypeError):
        return None

def list_mapping_presets() -> list[str]:
    """
    Returns a list of available mapping preset names.
    """
    if not os.path.exists(MAPPING_PRESETS_DIR):
        return []

    return [f.replace(".json", "") for f in os.listdir(MAPPING_PRESETS_DIR) if f.endswith(".json")]

def is_first_launch() -> bool:
    """
    Checks if it's the first time the application is being launched by looking
    for a 'first_launch_complete' flag in the config.
    """
    if not os.path.exists(CONFIG_FILE_PATH):
        return True
    try:
        with open(CONFIG_FILE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            return not data.get("first_launch_complete", False)
    except (json.JSONDecodeError, FileNotFoundError):
        return True

def mark_first_launch_complete():
    """
    Sets the 'first_launch_complete' flag to true in the config file.
    """
    data = {}
    if os.path.exists(CONFIG_FILE_PATH):
        try:
            with open(CONFIG_FILE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            # If file is corrupted or unreadable, we'll create a new one.
            pass

    data["first_launch_complete"] = True

    if not os.path.exists("config"):
        os.makedirs("config")

    with open(CONFIG_FILE_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)