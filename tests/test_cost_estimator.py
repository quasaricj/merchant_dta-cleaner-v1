import unittest
from src.core.cost_estimator import CostEstimator, API_COSTS

class TestCostEstimator(unittest.TestCase):

    def test_estimate_cost_basic_mode(self):
        """Test cost estimation for the Basic processing mode."""
        num_rows = 100
        model_name = "models/gemini-2.0-flash"  # A sample model name
        gemini_cost = CostEstimator.get_model_cost(model_name)
        expected_cost_per_row = gemini_cost + API_COSTS['google_search_per_query']
        expected_total_cost = num_rows * expected_cost_per_row
        self.assertAlmostEqual(
            CostEstimator.estimate_cost(num_rows, "Basic", model_name),
            expected_total_cost
        )

    def test_estimate_cost_enhanced_mode(self):
        """Test cost estimation for the Enhanced processing mode."""
        num_rows = 100
        model_name = "models/gemini-2.0-flash"  # A sample model name
        gemini_cost = CostEstimator.get_model_cost(model_name)
        expected_cost_per_row = (
            gemini_cost +
            API_COSTS['google_search_per_query'] +
            API_COSTS['google_places_find_place']
        )
        expected_total_cost = num_rows * expected_cost_per_row
        self.assertAlmostEqual(
            CostEstimator.estimate_cost(num_rows, "Enhanced", model_name),
            expected_total_cost
        )

    def test_estimate_cost_zero_rows(self):
        """Test that the cost is zero for zero rows."""
        self.assertEqual(CostEstimator.estimate_cost(0, "Basic", "any-model"), 0.0)
        self.assertEqual(CostEstimator.estimate_cost(0, "Enhanced", "any-model"), 0.0)

    def test_estimate_cost_no_model(self):
        """Test that cost is zero if no model is provided."""
        self.assertEqual(CostEstimator.estimate_cost(100, "Basic", None), 0.0)

    def test_check_budget_within_limits(self):
        """Test the budget check when the cost is within the allowed budget."""
        self.assertTrue(CostEstimator.check_budget(2.25, 100, 0.03))

    def test_check_budget_exceeds_limits(self):
        """Test the budget check when the cost exceeds the allowed budget."""
        self.assertFalse(CostEstimator.check_budget(4.00, 100, 0.03))

    def test_check_budget_zero_rows(self):
        """Test that the budget check always passes for zero rows."""
        self.assertTrue(CostEstimator.check_budget(0, 0, 0.01))

if __name__ == '__main__':
    unittest.main()