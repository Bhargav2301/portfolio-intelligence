from __future__ import annotations

from collections.abc import Iterable
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from portfolio_intelligence.domain.models import Position, Transaction, TransactionType


class DuplicateTransactionError(ValueError):
    pass


class InvalidLedgerOperation(ValueError):
    pass


class PortfolioLedger:
    """Append-only in-memory ledger used by the domain and initial API adapter."""

    def __init__(self) -> None:
        self._events: list[Transaction] = []
        self._idempotency_keys: set[str] = set()
        self._event_ids: set[UUID] = set()
        self._reversed_ids: set[UUID] = set()

    @property
    def events(self) -> tuple[Transaction, ...]:
        return tuple(self._events)

    def append(self, transaction: Transaction) -> Transaction:
        if transaction.idempotency_key in self._idempotency_keys:
            raise DuplicateTransactionError(transaction.idempotency_key)
        if transaction.id in self._event_ids:
            raise DuplicateTransactionError(str(transaction.id))

        if transaction.transaction_type is TransactionType.REVERSAL:
            self._validate_reversal(transaction)
        elif transaction.transaction_type is TransactionType.SELL:
            active_events = [
                event
                for event in self._events
                if event.portfolio_id == transaction.portfolio_id
                and event.id not in self._reversed_ids
            ]
            fold_positions([*active_events, transaction])

        self._events.append(transaction)
        self._idempotency_keys.add(transaction.idempotency_key)
        self._event_ids.add(transaction.id)
        if transaction.reverses_transaction_id is not None:
            self._reversed_ids.add(transaction.reverses_transaction_id)
        return transaction

    def reverse(
        self,
        transaction_id: UUID,
        *,
        idempotency_key: str,
        occurred_at: datetime | None = None,
    ) -> Transaction:
        original = next((event for event in self._events if event.id == transaction_id), None)
        if original is None:
            raise InvalidLedgerOperation("transaction to reverse does not exist")
        if transaction_id in self._reversed_ids:
            raise InvalidLedgerOperation("transaction has already been reversed")
        reversal = Transaction(
            id=uuid4(),
            portfolio_id=original.portfolio_id,
            instrument_id=original.instrument_id,
            transaction_type=TransactionType.REVERSAL,
            quantity=original.quantity,
            unit_price=original.unit_price,
            fees=original.fees,
            currency=original.currency,
            occurred_at=occurred_at or datetime.now(UTC),
            idempotency_key=idempotency_key,
            reverses_transaction_id=original.id,
            metadata={"reversal_of": str(original.id)},
        )
        return self.append(reversal)

    def positions(self, portfolio_id: UUID) -> dict[UUID, Position]:
        events = [event for event in self._events if event.portfolio_id == portfolio_id]
        active_events = [event for event in events if event.id not in self._reversed_ids]
        return fold_positions(active_events)

    def _validate_reversal(self, reversal: Transaction) -> None:
        target_id = reversal.reverses_transaction_id
        if target_id not in self._event_ids:
            raise InvalidLedgerOperation("transaction to reverse does not exist")
        if target_id in self._reversed_ids:
            raise InvalidLedgerOperation("transaction has already been reversed")
        original = next(event for event in self._events if event.id == target_id)
        if original.portfolio_id != reversal.portfolio_id:
            raise InvalidLedgerOperation("reversal portfolio does not match original")
        projected_events = [
            event
            for event in self._events
            if event.portfolio_id == original.portfolio_id
            and event.id not in self._reversed_ids
            and event.id != target_id
        ]
        try:
            fold_positions(projected_events)
        except InvalidLedgerOperation as error:
            raise InvalidLedgerOperation(
                "reversal would invalidate a dependent ledger event"
            ) from error


def fold_positions(events: Iterable[Transaction]) -> dict[UUID, Position]:
    state: dict[UUID, Position] = {}
    ordered = sorted(
        events,
        key=lambda event: (event.occurred_at, event.recorded_at, str(event.id)),
    )

    for event in ordered:
        if event.transaction_type in {
            TransactionType.REVERSAL,
            TransactionType.DIVIDEND,
            TransactionType.FEE,
        }:
            continue

        current = state.get(
            event.instrument_id,
            Position(
                instrument_id=event.instrument_id,
                quantity=Decimal("0"),
                average_cost=Decimal("0"),
                cost_basis=Decimal("0"),
                realized_gain=Decimal("0"),
            ),
        )

        if event.transaction_type is TransactionType.BUY:
            purchase_cost = event.quantity * event.unit_price + event.fees
            new_quantity = current.quantity + event.quantity
            new_cost_basis = current.cost_basis + purchase_cost
            average_cost = (
                new_cost_basis / new_quantity if new_quantity else Decimal("0")
            )
            state[event.instrument_id] = replace(
                current,
                quantity=new_quantity,
                cost_basis=new_cost_basis,
                average_cost=average_cost,
            )
            continue

        if event.quantity > current.quantity:
            raise InvalidLedgerOperation("ledger contains a sale larger than the position")
        released_cost = current.average_cost * event.quantity
        proceeds = event.quantity * event.unit_price - event.fees
        new_quantity = current.quantity - event.quantity
        state[event.instrument_id] = replace(
            current,
            quantity=new_quantity,
            cost_basis=current.cost_basis - released_cost,
            average_cost=current.average_cost if new_quantity else Decimal("0"),
            realized_gain=current.realized_gain + proceeds - released_cost,
        )

    return {
        instrument_id: position
        for instrument_id, position in state.items()
        if position.quantity
    }
