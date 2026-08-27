from __future__ import annotations

import sys
import unittest
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from portfolio_agents.evidence import numeric_citation_coverage
from portfolio_agents.graph import validate_output


class EvidenceGateTests(unittest.TestCase):
    def test_numeric_claim_requires_matching_value_and_evidence_id(self) -> None:
        citation = {
            "claim_key": "current_value",
            "evidence_id": "evidence-1",
            "value": "4000000.00000000",
            "unit": "INR",
            "as_of": "2026-08-26T00:00:00+00:00",
            "locator": "/v1/evidence/evidence-1",
        }
        coverage, missing = numeric_citation_coverage(
            "Portfolio value is INR 4000000.00000000 [evidence-1].", [citation]
        )
        self.assertEqual(coverage, Decimal("1"))
        self.assertEqual(missing, [])

        coverage, missing = numeric_citation_coverage(
            "Portfolio value is INR 5000000 [evidence-1].", [citation]
        )
        self.assertEqual(coverage, Decimal("0"))
        self.assertEqual(missing, ["5000000"])

    def test_output_is_suppressed_when_a_number_has_no_citation(self) -> None:
        result = validate_output(
            {
                "answer": "The unsupported forecast is 42 percent.",
                "citations": [],
                "stages": [],
                "limitations": [],
                "proposal": {
                    "type": "review",
                    "status": "proposal_only",
                    "candidate_actions": [{"action": "inspect"}],
                    "can_execute": False,
                },
                "policy": {"decision": "allow_analysis", "reasons": []},
                "telemetry": {},
            }
        )
        self.assertEqual(result["policy"]["decision"], "suppress_unsupported")
        self.assertEqual(result["proposal"]["candidate_actions"], [])
        self.assertIn("withheld", result["answer"])
        self.assertEqual(result["telemetry"]["numeric_citation_coverage"], "0")


if __name__ == "__main__":
    unittest.main()
