import unittest
from src.core.cost_estimator import CostEstimator, API_COSTS

class TestCostEstimator(unittest.TestCase):

    def test_estimate_cost_basic_mode(self):
        """Test cost estimation for Basic mode."""
        num_rows = 100
        mode = "Basic"

        expected_cost_per_row = API_COSTS['gemini_flash'] + API_COSTS['google_search']
        expected_total_cost = num_rows * expected_cost_per_row

        estimated_cost = CostEstimator.estimate_cost(num_rows, mode)

        self.assertAlmostEqual(estimated_cost, expected_total_cost)

    def test_estimate_cost_enhanced_mode(self):
        """Test cost estimation for Enhanced mode."""
        num_rows = 100
        mode = "Enhanced"

        expected_cost_per_row = API_COSTS['gemini_flash'] + API_COSTS['google_search'] + API_COSTS['google_places']
        expected_total_cost = num_rows * expected_cost_per_row

        estimated_cost = CostEstimator.estimate_cost(num_rows, mode)

        self.assertAlmostEqual(estimated_cost, expected_total_cost)

    def test_estimate_cost_zero_rows(self):
        """Test cost estimation with zero rows."""
        self.assertEqual(CostEstimator.estimate_cost(0, "Basic"), 0.0)
        self.assertEqual(CostEstimator.estimate_cost(0, "Enhanced"), 0.0)

    def test_check_budget_within_limit(self):
        """Test budget check when cost is within the limit."""
        num_rows = 100
        estimated_cost = 250.0 # 2.5 per row
        budget_per_row = 3.0

        self.assertTrue(CostEstimator.check_budget(estimated_cost, num_rows, budget_per_row))

    def test_check_budget_exceeds_limit(self):
        """Test budget check when cost exceeds the limit."""
        num_rows = 100
        estimated_cost = 350.0 # 3.5 per row
        budget_per_row = 3.0

        self.assertFalse(CostEstimator.check_budget(estimated_cost, num_rows, budget_per_row))

    def test_check_budget_at_limit(self):
        """Test budget check when cost is exactly at the limit."""
        num_rows = 100
        estimated_cost = 300.0 # 3.0 per row
        budget_per_row = 3.0

        self.assertTrue(CostEstimator.check_budget(estimated_cost, num_rows, budget_per_row))

    def test_check_budget_zero_rows(self):
        """Test budget check with zero rows, which should always be true."""
        self.assertTrue(CostEstimator.check_budget(100.0, 0, 3.0))

if __name__ == '__main__':
    unittest.main()