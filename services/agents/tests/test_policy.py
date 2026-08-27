from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from portfolio_agents.policy import evaluate_request, safe_response_text


class PolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.partial_snapshot = {
            "quality_state": "partial",
            "rules": {
                "equal_weighting_allowed": False,
                "protected_cash": {"amount": "2500000.00", "currency": "INR"},
            },
        }

    def test_order_execution_is_suppressed(self) -> None:
        decision = evaluate_request("Place an order for this stock", self.partial_snapshot)
        self.assertEqual(decision.decision, "suppress_execution")
        self.assertIn("ORDER_EXECUTION_PROHIBITED", decision.reasons)

    def test_partial_data_limits_analysis(self) -> None:
        decision = evaluate_request("What should I review?", self.partial_snapshot)
        self.assertEqual(decision.decision, "limited")

    def test_rules_are_exposed_as_limitations(self) -> None:
        decision = evaluate_request("Compare scenarios", self.partial_snapshot)
        self.assertTrue(any("Equal-weight" in item for item in decision.limitations))
        self.assertTrue(any("2500000.00" in item for item in decision.limitations))

    def test_imperative_language_is_rewritten(self) -> None:
        result = safe_response_text("You should buy the asset and execute the trade.")
        self.assertNotIn("should buy", result.lower())
        self.assertNotIn("execute the trade", result.lower())


if __name__ == "__main__":
    unittest.main()
