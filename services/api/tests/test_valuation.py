from __future__ import annotations

import sys
import unittest
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from portfolio_api.services.valuation import (
    SnapshotPoint,
    calculate_point_in_time_valuation,
    calculate_return_and_risk,
    calculate_xirr,
    run_market_stress_scenario,
)


def at(day: int) -> datetime:
    return datetime(2026, 1, day, 12, tzinfo=UTC)


def transaction(event_type: str, day: int, **values: object) -> SimpleNamespace:
    defaults: dict[str, object] = {
        "id": f"event-{day}-{event_type}",
        "event_type": event_type,
        "trade_date": at(day),
        "recorded_at": at(day),
        "gross_amount": Decimal("0"),
        "cash_delta": None,
        "instrument_reference": None,
        "quantity": None,
        "price": None,
        "currency": "INR",
        "ledger_version": day,
    }
    defaults.update(values)
    return SimpleNamespace(**defaults)


class ValuationGoldenTests(unittest.TestCase):
    def test_split_dividend_and_price_are_deterministic(self) -> None:
        events = [
            transaction("cash_deposit", 1, gross_amount=Decimal("1000")),
            transaction(
                "buy",
                1,
                instrument_reference="TEST.NS",
                quantity=Decimal("10"),
                price=Decimal("10"),
                gross_amount=Decimal("100"),
            ),
        ]
        actions = [
            SimpleNamespace(
                id="split",
                instrument_reference="TEST.NS",
                action_type="split",
                effective_at=at(2),
                known_at=at(2),
                split_factor=Decimal("2"),
                cash_amount_per_unit=None,
                currency="INR",
            ),
            SimpleNamespace(
                id="dividend",
                instrument_reference="TEST.NS",
                action_type="cash_dividend",
                effective_at=at(3),
                known_at=at(3),
                split_factor=None,
                cash_amount_per_unit=Decimal("1"),
                currency="INR",
            ),
        ]
        prices = [
            SimpleNamespace(
                instrument_reference="TEST.NS",
                observed_at=at(3),
                known_at=at(3),
                close_price=Decimal("6"),
                currency="INR",
                source_hash="a" * 64,
            )
        ]

        result = calculate_point_in_time_valuation(
            events,
            prices,
            actions,
            as_of=at(3),
            known_at=at(4),
            base_currency="INR",
            protected_cash=Decimal("0"),
        )

        self.assertEqual(result["cash_balance"], Decimal("920"))
        self.assertEqual(result["securities_market_value"], Decimal("120"))
        self.assertEqual(result["total_value"], Decimal("1040"))
        self.assertEqual(result["positions"][0]["quantity"], Decimal("20"))
        self.assertEqual(result["positions"][0]["cost_basis"], Decimal("100"))
        self.assertEqual(result["quality_state"], "trusted")

    def test_future_known_price_does_not_leak_into_historical_snapshot(self) -> None:
        events = [
            transaction("cash_deposit", 1, gross_amount=Decimal("100")),
            transaction(
                "buy",
                1,
                instrument_reference="TEST.NS",
                quantity=Decimal("1"),
                price=Decimal("10"),
                gross_amount=Decimal("10"),
            ),
        ]
        prices = [
            SimpleNamespace(
                instrument_reference="TEST.NS",
                observed_at=at(2),
                known_at=at(2),
                close_price=Decimal("11"),
                currency="INR",
                source_hash="a" * 64,
            ),
            SimpleNamespace(
                instrument_reference="TEST.NS",
                observed_at=at(3),
                known_at=at(5),
                close_price=Decimal("99"),
                currency="INR",
                source_hash="b" * 64,
            ),
        ]
        result = calculate_point_in_time_valuation(
            events,
            prices,
            [],
            as_of=at(3),
            known_at=at(4),
            base_currency="INR",
            protected_cash=Decimal("0"),
        )
        self.assertEqual(result["positions"][0]["price"], Decimal("11"))
        self.assertEqual(result["total_value"], Decimal("101"))

    def test_chain_linked_return_and_drawdown_golden_values(self) -> None:
        result = calculate_return_and_risk(
            [
                SnapshotPoint(at(1), Decimal("100")),
                SnapshotPoint(at(2), Decimal("110")),
                SnapshotPoint(at(3), Decimal("99")),
            ]
        )
        self.assertEqual(result["time_weighted_return"], Decimal("-0.01"))
        self.assertEqual(result["max_drawdown"], Decimal("-0.1"))
        self.assertIsNotNone(result["volatility"])
        self.assertIsNotNone(result["downside_deviation"])

    def test_money_weighted_return_one_year_golden_value(self) -> None:
        result = calculate_xirr(
            [(at(1), Decimal("-1000")), (at(1).replace(year=2027), Decimal("1100"))]
        )
        self.assertIsNotNone(result)
        assert result is not None
        self.assertAlmostEqual(float(result), 0.1, places=3)

    def test_transfer_out_uses_published_transfer_value_as_external_flow(self) -> None:
        result = calculate_point_in_time_valuation(
            [
                transaction(
                    "transfer_in",
                    1,
                    instrument_reference="TEST.NS",
                    quantity=Decimal("10"),
                    price=Decimal("10"),
                ),
                transaction(
                    "transfer_out",
                    2,
                    instrument_reference="TEST.NS",
                    quantity=Decimal("2"),
                    price=Decimal("15"),
                ),
            ],
            [
                SimpleNamespace(
                    instrument_reference="TEST.NS",
                    observed_at=at(2),
                    known_at=at(2),
                    close_price=Decimal("15"),
                    currency="INR",
                    source_hash="a" * 64,
                )
            ],
            [],
            as_of=at(2),
            known_at=at(3),
            base_currency="INR",
            protected_cash=Decimal("0"),
        )
        self.assertEqual(result["net_invested_capital"], Decimal("70"))
        self.assertEqual(
            result["external_flows"], [(at(1), Decimal("100")), (at(2), Decimal("-30"))]
        )

    def test_scenario_blocks_reserve_and_equal_weighting(self) -> None:
        result = run_market_stress_scenario(
            [
                {"instrument_reference": "A.NS", "market_value": Decimal("100")},
                {"instrument_reference": "B.NS", "market_value": Decimal("100")},
            ],
            cash_balance=Decimal("100"),
            protected_cash=Decimal("90"),
            price_shocks={"*": Decimal("-0.2")},
            allocations={"A.NS": Decimal("10"), "B.NS": Decimal("10")},
            max_position_weight_percent=Decimal("60"),
            equal_weighting_allowed=False,
        )
        self.assertEqual(result["status"], "blocked")
        self.assertFalse(result["can_execute"])
        self.assertEqual(
            {item["code"] for item in result["constraints"] if item["state"] == "blocked"},
            {"PROTECTED_CASH_BREACH", "EQUAL_WEIGHTING_PROHIBITED"},
        )

    def test_scenario_treats_max_position_weight_as_hard_constraint(self) -> None:
        result = run_market_stress_scenario(
            [{"instrument_reference": "A.NS", "market_value": Decimal("90")}],
            cash_balance=Decimal("10"),
            protected_cash=Decimal("10"),
            price_shocks={"A.NS": Decimal("0.5")},
            allocations={},
            max_position_weight_percent=Decimal("80"),
            equal_weighting_allowed=False,
        )
        self.assertEqual(result["status"], "blocked")
        self.assertIn(
            "MAX_POSITION_WEIGHT_EXCEEDED",
            {item["code"] for item in result["constraints"] if item["state"] == "blocked"},
        )


if __name__ == "__main__":
    unittest.main()
