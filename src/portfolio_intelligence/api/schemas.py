from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from portfolio_intelligence.domain.models import (
    AdviceClassification,
    EvidenceTier,
    Stance,
    TransactionType,
)


class TransactionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    instrument_id: UUID
    transaction_type: TransactionType
    quantity: Decimal = Field(ge=0)
    unit_price: Decimal = Field(ge=0)
    currency: str = Field(min_length=3, max_length=3)
    occurred_at: datetime
    idempotency_key: str = Field(min_length=1, max_length=200)
    fees: Decimal = Field(default=Decimal("0"), ge=0)


class EvidenceIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    publisher: str
    source_uri: str
    title: str
    source_tier: EvidenceTier
    published_at: datetime
    retrieved_at: datetime
    content_excerpt: str
    content_hash: str = Field(min_length=64, max_length=64)


class RecommendationIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    classification: AdviceClassification
    requested_stance: Stance
    instrument_id: UUID
    as_of: datetime
    market_data_as_of: datetime
    evidence: list[EvidenceIn]
    factual_claim_count: int = Field(ge=0)
    cited_claim_count: int = Field(ge=0)
    suitability_complete: bool = False
    conflicts_detected: bool = False

