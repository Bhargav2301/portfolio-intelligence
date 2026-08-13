from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from enum import IntEnum, StrEnum
from typing import Any
from uuid import UUID, uuid4


class AssetType(StrEnum):
    EQUITY = "equity"
    CRYPTO = "crypto"
    CASH = "cash"
    OTHER = "other"


class TransactionType(StrEnum):
    BUY = "buy"
    SELL = "sell"
    DIVIDEND = "dividend"
    FEE = "fee"
    REVERSAL = "reversal"


class EvidenceTier(IntEnum):
    PRIMARY = 1
    PROFESSIONAL_NEWS = 2
    RESEARCH = 3
    DISCOVERY_ONLY = 4


class AdviceClassification(StrEnum):
    ATTENTION_FLAG = "attention_flag"
    RESEARCH_RATING = "research_rating"
    PERSONALIZED_ADVICE = "personalized_advice"


class Stance(StrEnum):
    BUY = "buy"
    HOLD = "hold"
    REDUCE = "reduce"
    SELL = "sell"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


@dataclass(frozen=True, slots=True)
class Instrument:
    id: UUID
    symbol: str
    asset_type: AssetType
    currency: str
    isin: str | None = None
    mic: str | None = None
    chain_id: str | None = None
    contract_address: str | None = None


@dataclass(frozen=True, slots=True)
class Transaction:
    portfolio_id: UUID
    instrument_id: UUID
    transaction_type: TransactionType
    quantity: Decimal
    unit_price: Decimal
    currency: str
    occurred_at: datetime
    idempotency_key: str
    fees: Decimal = Decimal("0")
    id: UUID = field(default_factory=uuid4)
    recorded_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    reverses_transaction_id: UUID | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.quantity < 0:
            raise ValueError("quantity must not be negative")
        if self.unit_price < 0:
            raise ValueError("unit_price must not be negative")
        if self.fees < 0:
            raise ValueError("fees must not be negative")
        if not self.idempotency_key.strip():
            raise ValueError("idempotency_key is required")
        if self.occurred_at.tzinfo is None:
            raise ValueError("occurred_at must be timezone-aware")
        if (
            self.transaction_type is TransactionType.REVERSAL
            and self.reverses_transaction_id is None
        ):
            raise ValueError("a reversal must reference the original transaction")


@dataclass(frozen=True, slots=True)
class PriceObservation:
    instrument_id: UUID
    price: Decimal
    currency: str
    source: str
    effective_at: datetime
    received_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        if self.price < 0:
            raise ValueError("price must not be negative")
        if self.effective_at.tzinfo is None or self.received_at.tzinfo is None:
            raise ValueError("price timestamps must be timezone-aware")


@dataclass(frozen=True, slots=True)
class Position:
    instrument_id: UUID
    quantity: Decimal
    average_cost: Decimal
    cost_basis: Decimal
    realized_gain: Decimal


@dataclass(frozen=True, slots=True)
class ValuedPosition:
    position: Position
    market_price: Decimal
    market_value: Decimal
    unrealized_gain: Decimal
    price_source: str
    price_as_of: datetime
