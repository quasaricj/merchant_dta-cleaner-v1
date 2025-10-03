"""
This module provides a stateless utility class for estimating the cost of a
processing job based on the number of rows and the selected processing mode.
It is the single source of truth for all API-related costs.
"""

# Source of truth for API costs, based on research from October 2025.
# All costs are in USD per single unit (e.g., per request or per 1000 tokens).
API_COSTS = {
    # Gemini 2.0 Flash:
    # - Input: $0.10 per 1M tokens
    # - Output: $0.40 per 1M tokens
    # We estimate an average of 1000 input and 1000 output tokens per cleaning request.
    # Cost = (1000/1M * 0.10) + (1000/1M * 0.40) = $0.0001 + $0.0004 = $0.0005
    "gemini_flash_per_request": 0.0005,

    # Google Custom Search API:
    # - $5.00 per 1000 queries = $0.005 per query
    "google_search_per_query": 0.005,

    # Google Places API (Legacy Find Place):
    # - $17.00 per 1000 requests = $0.017 per request
    "google_places_find_place": 0.017
}


class CostEstimator:
    """
    Calculates the estimated cost for a processing job.
    """

    @staticmethod
    def estimate_cost(num_rows: int, mode: str) -> float:
        """
        Estimates the total cost for a given number of rows and processing mode.

        Args:
            num_rows: The number of rows to be processed.
            mode: The processing mode ("Basic" or "Enhanced").

        Returns:
            The total estimated cost.
        """
        if num_rows <= 0:
            return 0.0

        # Estimate the average cost per row based on the mode.
        # This is an approximation, assuming every row requires one of each call type.
        # The actual number of calls can vary based on the search logic.
        cost_per_row = (
            API_COSTS['gemini_flash_per_request'] +
            API_COSTS['google_search_per_query']
        )

        if mode == "Enhanced":
            # In Enhanced mode, we assume a Places API call is also made for every row.
            cost_per_row += API_COSTS['google_places_find_place']

        total_cost = num_rows * cost_per_row
        return total_cost

    @staticmethod
    def check_budget(estimated_cost: float, num_rows: int, budget_per_row: float) -> bool:
        """
        Checks if the estimated cost is within the per-row budget.

        Args:
            estimated_cost: The total estimated cost.
            num_rows: The number of rows.
            budget_per_row: The maximum allowed cost per row.

        Returns:
            True if the cost is within budget, False otherwise.
        """
        if num_rows <= 0:
            return True

        return (estimated_cost / num_rows) <= budget_per_row