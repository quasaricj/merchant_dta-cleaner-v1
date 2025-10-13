import unittest
from src.core.cost_estimator import CostEstimator

class TestCostEstimator(unittest.TestCase):

    def test_token_counting(self):
        """Test the simplified token counting mechanism."""
        self.assertEqual(CostEstimator.count_tokens(""), 0)
        self.assertEqual(CostEstimator.count_tokens("a"), 1)
        self.assertEqual(CostEstimator.count_tokens("abc"), 1)
        self.assertEqual(CostEstimator.count_tokens("abcd"), 1)
        self.assertEqual(CostEstimator.count_tokens("abcde"), 2)
        self.assertEqual(CostEstimator.count_tokens("This is a test."), 4)

    def test_calculate_prompt_cost(self):
        """Verify the cost calculation for a single prompt is correct."""
        # Using the default model "gemini-2.5-flash"
        # Input: $0.30 per 1M tokens
        # Output: $2.50 per 1M tokens

        # Test Case 1: Simple prompt
        input_tokens = 1000
        output_tokens = 200
        expected_cost = (1000 / 1_000_000 * 0.30) + (200 / 1_000_000 * 2.50)
        # 0.0003 + 0.0005 = 0.0008
        self.assertAlmostEqual(
            CostEstimator.calculate_prompt_cost("gemini-2.5-flash", input_tokens, output_tokens),
            expected_cost
        )

        # Test Case 2: Large prompt
        input_tokens = 500_000
        output_tokens = 50_000
        expected_cost = (500_000 / 1_000_000 * 0.30) + (50_000 / 1_000_000 * 2.50)
        # 0.15 + 0.125 = 0.275
        self.assertAlmostEqual(
            CostEstimator.calculate_prompt_cost("gemini-2.5-flash", input_tokens, output_tokens),
            expected_cost
        )

    def test_overall_estimation_is_reasonable(self):
        """
        Ensure the overall estimate_cost function produces a non-zero, reasonable value.
        """
        # A 100-row job should have a cost greater than 0
        estimated_cost = CostEstimator.estimate_cost(100, "Basic", "gemini-2.5-flash")
        self.assertGreater(estimated_cost, 0)

        # The cost for an enhanced job should be higher than a basic one
        enhanced_cost = CostEstimator.estimate_cost(100, "Enhanced", "gemini-2.5-flash")
        self.assertGreater(enhanced_cost, estimated_cost)

if __name__ == '__main__':
    unittest.main()