"""
This module provides a stateless utility class for estimating the cost of a
processing job based on the number of rows and the selected processing mode.
It is the single source of truth for all API-related costs.
"""
from typing import Optional

# Source of truth for non-model specific API costs, based on research from October 2025.
# All costs are in USD per single unit (e.g., per request or per query).
API_COSTS = {
    "google_search_per_query": 0.005,  # $5.00 per 1000 queries
    "google_places_find_place": 0.017, # $17.00 per 1000 requests
}

# Costs for different Gemini models. The key should be a substring of the model name from the API.
# We estimate an average of 1000 input and 1000 output tokens per cleaning request.
# Formula: Cost = ( (1000 / 1,000,000) * input_price ) + ( (1000 / 1,000,000) * output_price )
GEMINI_MODEL_COSTS = {
    "gemini-2.5-flash": { "per_request_estimate": (0.001 * 0.30) + (0.001 * 2.50) }, # ~$0.0028
    "gemini-2.0-flash": { "per_request_estimate": (0.001 * 0.10) + (0.001 * 0.40) }, # ~$0.0005
    "gemini-1.5-flash": { "per_request_estimate": (0.001 * 0.35) + (0.001 * 0.70) }, # Placeholder, ~$0.00105
    # Default for any other flash model that might appear
    "default_flash": { "per_request_estimate": 0.001 }
}

class CostEstimator:
    """Calculates the estimated cost for a processing job."""

    @staticmethod
    def get_model_cost(model_name: str) -> float:
        """Gets the estimated cost per request for a given Gemini model."""
        for key, costs in GEMINI_MODEL_COSTS.items():
            if key in model_name:
                return costs["per_request_estimate"]
        return GEMINI_MODEL_COSTS["default_flash"]["per_request_estimate"]

    @staticmethod
    def estimate_cost(num_rows: int, mode: str, model_name: Optional[str]) -> float:
        """Estimates the total cost for a given number of rows and processing mode."""
        if num_rows <= 0 or not model_name:
            return 0.0

        gemini_cost = CostEstimator.get_model_cost(model_name)
        cost_per_row = gemini_cost + API_COSTS['google_search_per_query']

        if mode == "Enhanced":
            cost_per_row += API_COSTS['google_places_find_place']

        total_cost = num_rows * cost_per_row
        return total_cost

    @staticmethod
    def check_budget(estimated_cost: float, num_rows: int, budget_per_row: float) -> bool:
        """Checks if the estimated cost is within the per-row budget."""
        if num_rows <= 0:
            return True
        return (estimated_cost / num_rows) <= budget_per_row