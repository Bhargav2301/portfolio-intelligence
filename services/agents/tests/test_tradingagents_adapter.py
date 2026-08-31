from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from portfolio_agents.tradingagents_adapter import derive_prediction


class TradingAgentsAdapterTests(unittest.TestCase):
    def test_positive_multi_horizon_evidence_produces_bullish_signal(self) -> None:
        evidence = [
            {
                "id": "research-1",
                "source_type": "market",
                "claims": [
                    {
                        "claim_key": "instrument.YATHARTH_HOSPITAL.return_1_week",
                        "statement": "One-week return.",
                        "numeric_value": "8.03",
                        "unit": "percent",
                    },
                    {
                        "claim_key": "instrument.YATHARTH_HOSPITAL.return_3_months",
                        "statement": "Three-month return.",
                        "numeric_value": "12.44",
                        "unit": "percent",
                    },
                    {
                        "claim_key": "instrument.YATHARTH_HOSPITAL.stock_score",
                        "statement": "Publisher stock score.",
                        "numeric_value": "8",
                        "unit": "score_10",
                    },
                    {
                        "claim_key": "instrument.YATHARTH_HOSPITAL.outlook",
                        "statement": "The publisher labels the security with a positive outlook.",
                        "numeric_value": None,
                        "unit": None,
                    },
                ],
            }
        ]
        result = derive_prediction(
            instrument="YATHARTH.NS",
            evidence=evidence,
            analyst_reports={"market": "completed"},
            perspectives={"bull": "completed", "conservative_risk": "completed"},
        )
        self.assertEqual(result.signal, "BULLISH")
        self.assertIn(result.confidence, {"medium", "high"})

    def test_missing_directional_evidence_abstains(self) -> None:
        result = derive_prediction(
            instrument="UNKNOWN.NS",
            evidence=[],
            analyst_reports={"market": "missing"},
            perspectives={"bear": "missing"},
        )
        self.assertEqual(result.signal, "ABSTAIN")
        self.assertEqual(result.confidence, "low")
        self.assertTrue(result.to_dict()["not_trade_instruction"])


if __name__ == "__main__":
    unittest.main()
