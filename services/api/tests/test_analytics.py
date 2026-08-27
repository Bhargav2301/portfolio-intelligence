from __future__ import annotations

import sys
import unittest
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from portfolio_api.services.analytics import GoalInputError, allocate_available_cash, required_cagr


class AnalyticsTests(unittest.TestCase):
    def test_two_x_in_ten_years(self) -> None:
        result = required_cagr("2", "10")
        self.assertAlmostEqual(float(result), 0.0717734625, places=9)

    def test_half_x_is_negative(self) -> None:
        result = required_cagr("0.5", "5")
        self.assertLess(result, Decimal(0))

    def test_invalid_horizon(self) -> None:
        with self.assertRaises(GoalInputError):
            required_cagr("2", "0")

    def test_protected_cash_is_not_available(self) -> None:
        self.assertEqual(
            allocate_available_cash(Decimal("3000000"), Decimal("2500000")),
            Decimal("500000"),
        )

    def test_protected_cash_cannot_make_available_cash_negative(self) -> None:
        self.assertEqual(
            allocate_available_cash(Decimal("1000000"), Decimal("2500000")),
            Decimal("0"),
        )


if __name__ == "__main__":
    unittest.main()
