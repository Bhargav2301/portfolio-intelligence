from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from portfolio_intelligence.domain.evidence import EvidenceItem, sha256_text
from portfolio_intelligence.domain.models import (
    AdviceClassification,
    EvidenceTier,
    Stance,
)
from portfolio_intelligence.domain.recommendation import (
    RecommendationPolicy,
    RecommendationRequest,
)


class RecommendationPolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now = datetime.now(UTC)
        content = "Exchange filing with a material audited result."
        self.evidence = EvidenceItem(
            publisher="Example Exchange",
            source_uri="https://exchange.example/filing/1",
            title="Audited results",
            source_tier=EvidenceTier.PRIMARY,
            published_at=self.now - timedelta(hours=1),
            retrieved_at=self.now,
            content_excerpt=content,
            content_hash=sha256_text(content),
        )
        self.policy = RecommendationPolicy(
            max_market_data_age=timedelta(minutes=15),
            max_evidence_age=timedelta(days=2),
        )

    def request(self, **overrides: object) -> RecommendationRequest:
        values: dict[str, object] = {
            "classification": AdviceClassification.ATTENTION_FLAG,
            "requested_stance": Stance.HOLD,
            "instrument_id": uuid4(),
            "as_of": self.now,
            "market_data_as_of": self.now - timedelta(minutes=1),
            "evidence": (self.evidence,),
            "factual_claim_count": 2,
            "cited_claim_count": 2,
        }
        values.update(overrides)
        return RecommendationRequest(**values)  # type: ignore[arg-type]

    def test_complete_attention_flag_passes(self) -> None:
        decision = self.policy.evaluate(self.request())
        self.assertTrue(decision.allowed)
        self.assertEqual(decision.final_stance, Stance.HOLD)

    def test_stale_market_data_fails_closed(self) -> None:
        decision = self.policy.evaluate(
            self.request(market_data_as_of=self.now - timedelta(hours=1))
        )
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.final_stance, Stance.INSUFFICIENT_EVIDENCE)
        self.assertIn("market data is stale", decision.reasons)

    def test_incomplete_citations_fail_closed(self) -> None:
        decision = self.policy.evaluate(self.request(cited_claim_count=1))
        self.assertFalse(decision.allowed)
        self.assertIn("claim evidence coverage is incomplete", decision.reasons)

    def test_personalized_advice_is_disabled_by_default(self) -> None:
        decision = self.policy.evaluate(
            self.request(
                classification=AdviceClassification.PERSONALIZED_ADVICE,
                suitability_complete=True,
            )
        )
        self.assertFalse(decision.allowed)
        self.assertIn("personalized advice is disabled", decision.reasons)

    def test_future_market_data_fails_closed(self) -> None:
        decision = self.policy.evaluate(
            self.request(market_data_as_of=self.now + timedelta(minutes=1))
        )
        self.assertFalse(decision.allowed)
        self.assertIn("market data is from after the requested as_of time", decision.reasons)

    def test_future_evidence_fails_closed(self) -> None:
        content = "A filing that was not available yet."
        future_evidence = EvidenceItem(
            publisher="Example Exchange",
            source_uri="https://exchange.example/filing/future",
            title="Future results",
            source_tier=EvidenceTier.PRIMARY,
            published_at=self.now + timedelta(minutes=1),
            retrieved_at=self.now + timedelta(minutes=1),
            content_excerpt=content,
            content_hash=sha256_text(content),
        )
        decision = self.policy.evaluate(self.request(evidence=(future_evidence,)))

        self.assertFalse(decision.allowed)
        self.assertIn("evidence was unavailable at the requested as_of time", decision.reasons)


if __name__ == "__main__":
    unittest.main()
