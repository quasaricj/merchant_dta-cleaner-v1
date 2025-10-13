"""
This module provides a stateless utility class for estimating the cost of a
processing job. It is the single source of truth for all API-related costs,
with granular estimates based on token counts for AI calls.
"""
from typing import Optional
import math

# Source of truth for non-model specific API costs, based on research from October 2025.
# All costs are in USD per single unit (e.g., per request or per query).
API_COSTS = {
    "google_search_per_query": 0.005,  # $5.00 per 1000 queries
    "google_places_find_place": 0.017, # $17.00 per 1000 requests
}

# Token-based pricing for Gemini Flash models, per 1,000,000 tokens.
# Based on Google's official pricing page as of October 2025.
GEMINI_TOKEN_COSTS = {
    "gemini-2.5-flash": {
        "input": 0.30,
        "output": 2.50
    },
    "default": {
        "input": 0.30,
        "output": 2.50
    }
}

# Average token counts for different types of prompts and their expected responses.
# These are used for pre-run estimation. A more accurate count is done at runtime.
AVERAGE_TOKEN_COUNTS = {
    "aggregator_removal": {"input": 200, "output": 50},
    "search_analysis": {"input": 1500, "output": 200},
    "website_verification": {"input": 4000, "output": 50}
}

class CostEstimator:
    """Calculates processing costs with token-based accuracy."""

    @staticmethod
    def _get_model_token_costs(model_name: str) -> dict:
        """Finds the token cost entry for a given model name."""
        for key, costs in GEMINI_TOKEN_COSTS.items():
            if key in model_name:
                return costs
        return GEMINI_TOKEN_COSTS["default"]

    @staticmethod
    def count_tokens(text: str) -> int:
        """
        A simplified token counting method.
        A common approximation is that 1 token is roughly 4 characters for English text.
        This provides a good enough estimate for cost calculation without a full tokenizer.
        """
        return math.ceil(len(text) / 4)

    @staticmethod
    def calculate_prompt_cost(model_name: str, input_tokens: int, output_tokens: int) -> float:
        """Calculates the cost of a single AI prompt based on token counts."""
        costs = CostEstimator._get_model_token_costs(model_name)
        input_cost = (input_tokens / 1_000_000) * costs["input"]
        output_cost = (output_tokens / 1_000_000) * costs["output"]
        return input_cost + output_cost

    @staticmethod
    def estimate_cost(num_rows: int, mode: str, model_name: Optional[str]) -> float:
        """
        Estimates the total cost for a job using a "maximum expected" model based on
        average token counts for each operation.
        """
        if num_rows <= 0 or not model_name:
            return 0.0

        # Estimate cost for one row assuming a worst-case scenario
        cost_per_row = 0
        # 1. Aggregator removal call
        cost_per_row += CostEstimator.calculate_prompt_cost(
            model_name,
            AVERAGE_TOKEN_COUNTS["aggregator_removal"]["input"],
            AVERAGE_TOKEN_COUNTS["aggregator_removal"]["output"]
        )
        # 2. Search calls (assume 4 searches for worst-case)
        cost_per_row += 4 * API_COSTS['google_search_per_query']
        # 3. Search analysis call
        cost_per_row += CostEstimator.calculate_prompt_cost(
            model_name,
            AVERAGE_TOKEN_COUNTS["search_analysis"]["input"],
            AVERAGE_TOKEN_COUNTS["search_analysis"]["output"]
        )
        # 4. Website verification call
        cost_per_row += CostEstimator.calculate_prompt_cost(
            model_name,
            AVERAGE_TOKEN_COUNTS["website_verification"]["input"],
            AVERAGE_TOKEN_COUNTS["website_verification"]["output"]
        )

        if mode == "Enhanced":
            cost_per_row += API_COSTS['google_places_find_place']

        return num_rows * cost_per_row

    @staticmethod
    def check_budget(estimated_cost: float, num_rows: int, budget_per_row: float) -> bool:
        """Checks if the estimated cost is within the per-row budget."""
        if num_rows <= 0:
            return True
        return (estimated_cost / num_rows) <= budget_per_row