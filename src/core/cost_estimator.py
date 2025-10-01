"""
This module provides a stateless utility class for estimating the cost of a
processing job based on the number of rows and the selected processing mode.
"""
from src.core.processing_engine import API_COSTS

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
        # This is an approximation as the actual number of API calls can vary per row.
        # We assume every row will use Gemini and at least one search.
        cost_per_row = API_COSTS['gemini_flash'] + API_COSTS['google_search']

        if mode == "Enhanced":
            # In Enhanced mode, we assume a Places API call is also made for every row.
            cost_per_row += API_COSTS['google_places']

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