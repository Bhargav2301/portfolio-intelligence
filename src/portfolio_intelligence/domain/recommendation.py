from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID

from portfolio_intelligence.domain.evidence import EvidenceItem
from portfolio_intelligence.domain.models import AdviceClassification, EvidenceTier, Stance


@dataclass(frozen=True, slots=True)
class RecommendationRequest:
    classification: AdviceClassification
    requested_stance: Stance
    instrument_id: UUID
    as_of: datetime
    market_data_as_of: datetime
    evidence: tuple[EvidenceItem, ...]
    factual_claim_count: int
    cited_claim_count: int
    suitability_complete: bool = False
    conflicts_detected: bool = False


@dataclass(frozen=True, slots=True)
class RecommendationDecision:
    final_stance: Stance
    allowed: bool
    reasons: tuple[str, ...]
    evidence_ids: tuple[UUID, ...]
    policy_version: str = "branch-c-v1"


@dataclass(frozen=True, slots=True)
class RecommendationPolicy:
    max_market_data_age: timedelta
    max_evidence_age: timedelta
    allow_personalized_advice: bool = False
    require_primary_source: bool = True

    def evaluate(self, request: RecommendationRequest) -> RecommendationDecision:
        reasons: list[str] = []

        if request.as_of.tzinfo is None or request.market_data_as_of.tzinfo is None:
            reasons.append("timestamps must be timezone-aware")
        elif request.market_data_as_of > request.as_of:
            reasons.append("market data is from after the requested as_of time")
        elif request.as_of - request.market_data_as_of > self.max_market_data_age:
            reasons.append("market data is stale")

        if not request.evidence:
            reasons.append("no evidence supplied")
        else:
            if any(
                item.published_at > request.as_of or item.retrieved_at > request.as_of
                for item in request.evidence
            ):
                reasons.append("evidence was unavailable at the requested as_of time")
            if any(
                request.as_of - item.published_at > self.max_evidence_age
                for item in request.evidence
            ):
                reasons.append("evidence is stale")
            if self.require_primary_source and not any(
                item.source_tier is EvidenceTier.PRIMARY for item in request.evidence
            ):
                reasons.append("no primary source supplied")
            if any(item.source_tier is EvidenceTier.DISCOVERY_ONLY for item in request.evidence):
                reasons.append("discovery-only evidence cannot support a recommendation")

        if request.factual_claim_count != request.cited_claim_count:
            reasons.append("claim evidence coverage is incomplete")
        if request.conflicts_detected:
            reasons.append("material evidence conflict detected")

        if request.classification is AdviceClassification.PERSONALIZED_ADVICE:
            if not self.allow_personalized_advice:
                reasons.append("personalized advice is disabled")
            if not request.suitability_complete:
                reasons.append("suitability assessment is incomplete")

        if reasons:
            return RecommendationDecision(
                final_stance=Stance.INSUFFICIENT_EVIDENCE,
                allowed=False,
                reasons=tuple(reasons),
                evidence_ids=tuple(item.id for item in request.evidence),
            )

        return RecommendationDecision(
            final_stance=request.requested_stance,
            allowed=True,
            reasons=("all policy gates passed",),
            evidence_ids=tuple(item.id for item in request.evidence),
        )
