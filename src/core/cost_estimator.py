"""
This module provides a stateless utility class for estimating the cost of a
processing job. It is the single source of truth for all API-related costs,
with granular estimates for different types of AI calls.
"""
from typing import Optional

# Source of truth for non-model specific API costs, based on research from October 2025.
# All costs are in USD per single unit (e.g., per request or per query).
API_COSTS = {
    "google_search_per_query": 0.005,  # $5.00 per 1000 queries
    "google_places_find_place": 0.017, # $17.00 per 1000 requests
}

# Costs for different Gemini models, broken down by the type of AI call.
# This allows for more accurate per-row cost tracking based on the actual operations performed.
# Estimates are based on typical prompt sizes for each task.
# 'utility' = small prompt (e.g., aggregator removal)
# 'verification' = medium prompt (e.g., website content check)
# 'analysis' = large prompt (e.g., analyzing search results)
GEMINI_MODEL_COSTS = {
    "gemini-1.5-flash": {
        "utility": 0.0005,
        "verification": 0.0010,
        "analysis": 0.0015,
        "default": 0.0010
    },
    # Defining costs for other potential models as well
    "gemini-2.0-flash": {
        "utility": 0.0004,
        "verification": 0.0008,
        "analysis": 0.0012,
        "default": 0.0008
    },
    "default_flash": {
        "utility": 0.0005,
        "verification": 0.0010,
        "analysis": 0.0015,
        "default": 0.0010
    }
}

class CostEstimator:
    """Calculates processing costs with granular, per-operation accuracy."""

    @staticmethod
    def get_model_cost(model_name: str, call_type: str = "default") -> float:
        """
        Gets the estimated cost for a specific type of AI call for a given Gemini model.

        Args:
            model_name: The name of the Gemini model being used.
            call_type: The type of call ('utility', 'verification', 'analysis').

        Returns:
            The cost in USD for that specific operation.
        """
        if not model_name:
            model_costs = GEMINI_MODEL_COSTS["default_flash"]
        else:
            # Find the matching model cost entry
            model_key_found = None
            for key in GEMINI_MODEL_COSTS:
                if key in model_name:
                    model_key_found = key
                    break
            model_costs = GEMINI_MODEL_COSTS.get(model_key_found, GEMINI_MODEL_COSTS["default_flash"])

        # Return the cost for the specific call type, or the default for that model
        return model_costs.get(call_type, model_costs["default"])

    @staticmethod
    def estimate_cost(num_rows: int, mode: str, model_name: Optional[str]) -> float:
        """
        Estimates the total cost for a job using a simplified "maximum expected" model.
        This is for pre-run estimation, not per-row final cost.
        """
        if num_rows <= 0 or not model_name:
            return 0.0

        # For estimation, we assume a worst-case scenario for an average row.
        # e.g., 1 utility call, 4 searches, 1 analysis, 1 verification
        cost_per_row = (
            CostEstimator.get_model_cost(model_name, "utility") +
            (4 * API_COSTS['google_search_per_query']) +
            CostEstimator.get_model_cost(model_name, "analysis") +
            CostEstimator.get_model_cost(model_name, "verification")
        )

        total_cost = num_rows * cost_per_row
        return total_cost

    @staticmethod
    def check_budget(estimated_cost: float, num_rows: int, budget_per_row: float) -> bool:
        """Checks if the estimated cost is within the per-row budget."""
        if num_rows <= 0:
            return True
        return (estimated_cost / num_rows) <= budget_per_row