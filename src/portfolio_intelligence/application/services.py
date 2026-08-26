from __future__ import annotations

from datetime import timedelta
from uuid import UUID

from portfolio_intelligence.config import Settings
from portfolio_intelligence.domain.ledger import PortfolioLedger
from portfolio_intelligence.domain.models import Position, Transaction
from portfolio_intelligence.domain.recommendation import (
    RecommendationDecision,
    RecommendationPolicy,
    RecommendationRequest,
)


class PortfolioService:
    def __init__(self, ledger: PortfolioLedger) -> None:
        self._ledger = ledger

    def record_transaction(self, transaction: Transaction) -> Transaction:
        return self._ledger.append(transaction)

    def positions(self, portfolio_id: UUID) -> dict[UUID, Position]:
        return self._ledger.positions(portfolio_id)


class RecommendationService:
    def __init__(self, policy: RecommendationPolicy) -> None:
        self._policy = policy

    @classmethod
    def from_settings(cls, settings: Settings) -> RecommendationService:
        return cls(
            RecommendationPolicy(
                max_market_data_age=timedelta(seconds=settings.market_data_max_age_seconds),
                max_evidence_age=timedelta(seconds=settings.evidence_max_age_seconds),
                allow_personalized_advice=settings.allow_personalized_advice,
            )
        )

    def evaluate(self, request: RecommendationRequest) -> RecommendationDecision:
        return self._policy.evaluate(request)

