from __future__ import annotations

import unittest
from datetime import UTC, datetime

from portfolio_intelligence.domain.evidence import EvidenceItem, EvidenceLedger, sha256_text
from portfolio_intelligence.domain.models import EvidenceTier


class EvidenceTests(unittest.TestCase):
    def test_hash_verifies_unchanged_content(self) -> None:
        content = "Exchange filing: audited revenue increased by 10%."
        evidence = EvidenceItem(
            publisher="Example Exchange",
            source_uri="https://exchange.example/filing/1",
            title="Audited results",
            source_tier=EvidenceTier.PRIMARY,
            published_at=datetime.now(UTC),
            retrieved_at=datetime.now(UTC),
            content_excerpt=content,
            content_hash=sha256_text(content),
        )

        self.assertTrue(evidence.verifies(content))
        self.assertFalse(evidence.verifies(content + " changed"))

    def test_duplicate_source_and_hash_is_deduplicated(self) -> None:
        content = "Material announcement"
        first = EvidenceItem(
            publisher="Example Exchange",
            source_uri="https://exchange.example/filing/1",
            title="Announcement",
            source_tier=EvidenceTier.PRIMARY,
            published_at=datetime.now(UTC),
            retrieved_at=datetime.now(UTC),
            content_excerpt=content,
            content_hash=sha256_text(content),
        )
        second = EvidenceItem(
            publisher=first.publisher,
            source_uri=first.source_uri,
            title=first.title,
            source_tier=first.source_tier,
            published_at=first.published_at,
            retrieved_at=first.retrieved_at,
            content_excerpt=first.content_excerpt,
            content_hash=first.content_hash,
        )
        ledger = EvidenceLedger()

        self.assertEqual(ledger.add_evidence(first).id, ledger.add_evidence(second).id)


if __name__ == "__main__":
    unittest.main()

