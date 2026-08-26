from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID, uuid4

from portfolio_intelligence.domain.models import EvidenceTier


@dataclass(frozen=True, slots=True)
class EvidenceItem:
    publisher: str
    source_uri: str
    title: str
    source_tier: EvidenceTier
    published_at: datetime
    retrieved_at: datetime
    content_excerpt: str
    content_hash: str
    entitlement: str = "internal-use"
    instrument_id: UUID | None = None
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        if self.published_at.tzinfo is None or self.retrieved_at.tzinfo is None:
            raise ValueError("evidence timestamps must be timezone-aware")
        if not self.source_uri.startswith(("https://", "s3://")):
            raise ValueError("evidence source must be an approved HTTPS or object-store URI")
        if len(self.content_hash) != 64:
            raise ValueError("content_hash must be a SHA-256 hex digest")

    def verifies(self, content: str) -> bool:
        return self.content_hash == sha256_text(content)


@dataclass(frozen=True, slots=True)
class Claim:
    text: str
    evidence_id: UUID
    id: UUID = field(default_factory=uuid4)


class EvidenceLedger:
    def __init__(self) -> None:
        self._evidence: dict[UUID, EvidenceItem] = {}
        self._claims: dict[UUID, Claim] = {}

    def add_evidence(self, evidence: EvidenceItem) -> EvidenceItem:
        duplicate = next(
            (
                item
                for item in self._evidence.values()
                if item.source_uri == evidence.source_uri
                and item.content_hash == evidence.content_hash
            ),
            None,
        )
        if duplicate is not None:
            return duplicate
        self._evidence[evidence.id] = evidence
        return evidence

    def add_claim(self, claim: Claim) -> Claim:
        if claim.evidence_id not in self._evidence:
            raise ValueError("claim references unknown evidence")
        self._claims[claim.id] = claim
        return claim

    def get_evidence(self, evidence_id: UUID) -> EvidenceItem | None:
        return self._evidence.get(evidence_id)

    def resolve_claims(self, claim_ids: tuple[UUID, ...]) -> tuple[tuple[Claim, EvidenceItem], ...]:
        resolved: list[tuple[Claim, EvidenceItem]] = []
        for claim_id in claim_ids:
            claim = self._claims.get(claim_id)
            if claim is None:
                raise ValueError(f"unknown claim {claim_id}")
            resolved.append((claim, self._evidence[claim.evidence_id]))
        return tuple(resolved)


def sha256_text(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()

