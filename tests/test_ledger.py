from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from portfolio_intelligence.domain.ledger import (
    DuplicateTransactionError,
    InvalidLedgerOperation,
    PortfolioLedger,
)
from portfolio_intelligence.domain.models import Transaction, TransactionType


class PortfolioLedgerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.portfolio_id = uuid4()
        self.instrument_id = uuid4()
        self.now = datetime.now(UTC)
        self.ledger = PortfolioLedger()

    def transaction(
        self,
        transaction_type: TransactionType,
        quantity: str,
        price: str,
        key: str,
        *,
        occurred_at: datetime | None = None,
        fees: str = "0",
    ) -> Transaction:
        return Transaction(
            portfolio_id=self.portfolio_id,
            instrument_id=self.instrument_id,
            transaction_type=transaction_type,
            quantity=Decimal(quantity),
            unit_price=Decimal(price),
            fees=Decimal(fees),
            currency="INR",
            occurred_at=occurred_at or self.now,
            idempotency_key=key,
        )

    def test_average_cost_and_realized_gain_are_deterministic(self) -> None:
        self.ledger.append(self.transaction(TransactionType.BUY, "10", "100", "buy-1"))
        self.ledger.append(
            self.transaction(
                TransactionType.BUY,
                "10",
                "120",
                "buy-2",
                occurred_at=self.now + timedelta(seconds=1),
            )
        )
        self.ledger.append(
            self.transaction(
                TransactionType.SELL,
                "5",
                "150",
                "sell-1",
                occurred_at=self.now + timedelta(seconds=2),
                fees="5",
            )
        )

        position = self.ledger.positions(self.portfolio_id)[self.instrument_id]

        self.assertEqual(position.quantity, Decimal("15"))
        self.assertEqual(position.average_cost, Decimal("110"))
        self.assertEqual(position.cost_basis, Decimal("1650"))
        self.assertEqual(position.realized_gain, Decimal("195"))

    def test_duplicate_idempotency_key_is_rejected(self) -> None:
        self.ledger.append(self.transaction(TransactionType.BUY, "1", "100", "same"))
        with self.assertRaises(DuplicateTransactionError):
            self.ledger.append(self.transaction(TransactionType.BUY, "1", "100", "same"))

    def test_sale_cannot_create_negative_position(self) -> None:
        with self.assertRaises(InvalidLedgerOperation):
            self.ledger.append(self.transaction(TransactionType.SELL, "1", "100", "sell"))

    def test_reversal_removes_original_effect_without_mutation(self) -> None:
        original = self.ledger.append(
            self.transaction(TransactionType.BUY, "5", "100", "buy")
        )
        self.ledger.reverse(original.id, idempotency_key="reverse-buy")

        self.assertEqual(self.ledger.positions(self.portfolio_id), {})
        self.assertEqual(len(self.ledger.events), 2)
        self.assertEqual(self.ledger.events[0], original)

    def test_reversal_cannot_invalidate_later_sale(self) -> None:
        original = self.ledger.append(
            self.transaction(TransactionType.BUY, "5", "100", "buy")
        )
        self.ledger.append(
            self.transaction(
                TransactionType.SELL,
                "5",
                "120",
                "sell",
                occurred_at=self.now + timedelta(seconds=1),
            )
        )

        with self.assertRaises(InvalidLedgerOperation):
            self.ledger.reverse(original.id, idempotency_key="reverse-buy")

    def test_backdated_sale_cannot_rely_on_a_later_buy(self) -> None:
        self.ledger.append(
            self.transaction(
                TransactionType.BUY,
                "5",
                "100",
                "buy",
                occurred_at=self.now + timedelta(days=1),
            )
        )

        with self.assertRaises(InvalidLedgerOperation):
            self.ledger.append(
                self.transaction(TransactionType.SELL, "5", "100", "backdated-sell")
            )


if __name__ == "__main__":
    unittest.main()
