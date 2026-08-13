from __future__ import annotations

import unittest
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from portfolio_intelligence.domain.analytics import value_positions
from portfolio_intelligence.domain.models import Position, PriceObservation


class AnalyticsTests(unittest.TestCase):
    def test_valuation_uses_explicit_observation_and_as_of(self) -> None:
        instrument_id = uuid4()
        as_of = datetime.now(UTC)
        position = Position(
            instrument_id=instrument_id,
            quantity=Decimal("10"),
            average_cost=Decimal("100"),
            cost_basis=Decimal("1000"),
            realized_gain=Decimal("0"),
        )
        price = PriceObservation(
            instrument_id=instrument_id,
            price=Decimal("125"),
            currency="INR",
            source="licensed-test-feed",
            effective_at=as_of,
        )

        valuation = value_positions(
            {instrument_id: position},
            {instrument_id: price},
            as_of=as_of,
        )

        self.assertEqual(valuation.total_market_value, Decimal("1250"))
        self.assertEqual(valuation.total_unrealized_gain, Decimal("250"))
        self.assertEqual(valuation.absolute_return, Decimal("0.25"))
        self.assertEqual(valuation.positions[0].price_source, "licensed-test-feed")


if __name__ == "__main__":
    unittest.main()

