import unittest
from src.core.cost_estimator import CostEstimator, API_COSTS

class TestCostEstimator(unittest.TestCase):

    def test_estimate_cost_basic_mode(self):
        """Test cost estimation for the Basic processing mode."""
        num_rows = 100
        expected_cost_per_row = (
            API_COSTS['gemini_flash_per_request'] +
            API_COSTS['google_search_per_query']
        )
        expected_total_cost = num_rows * expected_cost_per_row
        self.assertAlmostEqual(
            CostEstimator.estimate_cost(num_rows, "Basic"),
            expected_total_cost
        )

    def test_estimate_cost_enhanced_mode(self):
        """Test cost estimation for the Enhanced processing mode."""
        num_rows = 100
        expected_cost_per_row = (
            API_COSTS['gemini_flash_per_request'] +
            API_COSTS['google_search_per_query'] +
            API_COSTS['google_places_find_place']
        )
        expected_total_cost = num_rows * expected_cost_per_row
        self.assertAlmostEqual(
            CostEstimator.estimate_cost(num_rows, "Enhanced"),
            expected_total_cost
        )

    def test_estimate_cost_zero_rows(self):
        """Test that the cost is zero for zero rows."""
        self.assertEqual(CostEstimator.estimate_cost(0, "Basic"), 0.0)
        self.assertEqual(CostEstimator.estimate_cost(0, "Enhanced"), 0.0)

    def test_check_budget_within_limits(self):
        """Test the budget check when the cost is within the allowed budget."""
        # Cost per row is $0.0225, budget is $0.03
        self.assertTrue(CostEstimator.check_budget(2.25, 100, 0.03))

    def test_check_budget_exceeds_limits(self):
        """Test the budget check when the cost exceeds the allowed budget."""
        # Cost per row is $0.04, budget is $0.03
        self.assertFalse(CostEstimator.check_budget(4.00, 100, 0.03))

    def test_check_budget_zero_rows(self):
        """Test that the budget check always passes for zero rows."""
        self.assertTrue(CostEstimator.check_budget(0, 0, 0.01))

if __name__ == '__main__':
    unittest.main()