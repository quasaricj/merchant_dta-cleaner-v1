# pylint: disable=too-many-instance-attributes
"""
This module defines the core data structures (dataclasses) used throughout the application.
These structures represent the state of records, configurations, and job settings.
"""
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any

@dataclass
class MerchantRecord:
    """Represents a single row of merchant data, both input and output."""
    original_name: str
    original_address: Optional[str] = None
    original_city: Optional[str] = None
    original_country: Optional[str] = None
    original_state: Optional[str] = None
    cleaned_merchant_name: str = ""
    website: str = ""
    socials: List[str] = field(default_factory=list)
    evidence: str = ""
    evidence_links: List[str] = field(default_factory=list)
    cost_per_row: float = 0.0
    logo_filename: str = ""
    remarks: str = ""
    other_data: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ApiConfig:
    """Stores API keys required for the application."""
    gemini_api_key: str = ""
    search_api_key: str = ""
    search_cse_id: str = ""
    places_api_key: Optional[str] = None

    def is_valid(self) -> bool:
        """Checks if all mandatory API keys are present."""
        return bool(self.gemini_api_key and self.search_api_key and self.search_cse_id)

@dataclass
class ColumnMapping:
    """Defines the mapping from source Excel columns to required data fields."""
    merchant_name: str
    address: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    state: Optional[str] = None

@dataclass
class OutputColumnConfig:
    """Represents the configuration for a single output column."""
    source_field: str
    output_header: str
    enabled: bool = True
    is_custom: bool = False

def get_default_output_columns() -> List[OutputColumnConfig]:
    """Returns a default list of output column configurations based on FR4."""
    default_fields = [
        ("cleaned_merchant_name", "Cleaned Merchant Name"),
        ("website", "Website"),
        ("socials", "Social(s)"),
        ("evidence", "Evidence"),
        ("evidence_links", "Evidence Links"),
        ("cost_per_row", "Cost per Row"),
        ("logo_filename", "Logo Filename"),
        ("remarks", "Remarks"),
    ]
    return [OutputColumnConfig(source_field=sf, output_header=oh) for sf, oh in default_fields]

@dataclass
class JobSettings:
    """Contains all settings for a single processing job."""
    input_filepath: str
    output_filepath: str
    column_mapping: ColumnMapping
    start_row: int
    end_row: int
    mode: str
    model_name: Optional[str] = None
    budget_per_row: float = 3.0
    output_columns: List[OutputColumnConfig] = field(default_factory=get_default_output_columns)
    mock_mode: bool = False
    strict_match: bool = False