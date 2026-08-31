from __future__ import annotations

import asyncio
import os
import sys
import unittest
from pathlib import Path

from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
os.environ.pop("OPENAI_API_KEY", None)
os.environ.pop("OPENAI_MODEL", None)

from portfolio_agents.graph import graph
from portfolio_agents.main import AgentProposal


class AgentGraphTests(unittest.TestCase):
    def test_agent_proposal_cannot_enable_execution(self) -> None:
        with self.assertRaises(ValidationError):
            AgentProposal(
                type="rebalance_review",
                status="proposal_only",
                title="Review allocation",
                can_execute=True,
            )

    def test_incomplete_portfolio_is_bounded(self) -> None:
        result = asyncio.run(
            graph.ainvoke(
                {
                    "run_id": "test-run",
                    "tenant_id": "test-tenant",
                    "portfolio_id": "test-portfolio",
                    "as_of": "2026-08-26T00:00:00+00:00",
                    "question": "Place an order for equal weights",
                    "snapshot": {
                        "quality_state": "partial",
                        "metrics": {"current_value": None},
                        "rules": {
                            "equal_weighting_allowed": False,
                            "protected_cash": {
                                "amount": "2500000.00",
                                "currency": "INR",
                            },
                        },
                        "limitations": ["No approved ledger has been published."],
                    },
                    "stages": [],
                    "evidence": [],
                    "limitations": [],
                },
                config={"configurable": {"thread_id": "test-run"}},
            )
        )
        self.assertEqual(result["policy"]["decision"], "suppress_execution")
        self.assertIn("response_composed", result["stages"])
        self.assertIn("No trade was placed", result["answer"])
        self.assertIn("No approved ledger has been published.", result["limitations"])

    def test_tradingagents_adapter_proposes_review_without_execution(self) -> None:
        result = asyncio.run(
            graph.ainvoke(
                {
                    "run_id": "research-run",
                    "tenant_id": "test-tenant",
                    "portfolio_id": "test-portfolio",
                    "as_of": "2026-08-26T00:00:00+00:00",
                    "question": "Research the concentration risk in this stock",
                    "instrument": "RELIANCE.NS",
                    "snapshot": {
                        "quality_state": "trusted",
                        "metrics": {
                            "current_value": "4000000.00000000",
                            "cash_balance": "2500000.00000000",
                        },
                        "rules": {
                            "equal_weighting_allowed": False,
                            "protected_cash": {
                                "amount": "2500000.00",
                                "currency": "INR",
                            },
                        },
                        "limitations": [],
                    },
                    "context": {
                        "ledger": {
                            "holdings": [
                                {
                                    "instrument_reference": "RELIANCE.NS",
                                    "quantity": "1000.0000000000",
                                    "last_price": "1500.00000000",
                                    "weight_percent": "37.50",
                                    "unrealized_pnl": "0.00000000",
                                }
                            ]
                        },
                        "monitoring": {
                            "alerts": [
                                {
                                    "kind": "concentration",
                                    "severity": "warning",
                                    "instrument_reference": "RELIANCE.NS",
                                    "observed_value": "37.50",
                                    "threshold_value": "25.00",
                                }
                            ]
                        },
                        "evidence": [
                            {
                                "id": "ledger:snapshot",
                                "title": "Published ledger",
                                "uri": "/v1/portfolios/test/holdings",
                            }
                        ],
                    },
                    "stages": [],
                    "evidence": [],
                    "limitations": [],
                },
                config={"configurable": {"thread_id": "research-run"}},
            )
        )
        self.assertEqual(result["policy"]["decision"], "allow_analysis")
        self.assertEqual(result["proposal"]["type"], "rebalance_review")
        self.assertFalse(result["proposal"]["can_execute"])
        self.assertIn("asset_analysts_completed", result["stages"])
        self.assertIn("research_debate_completed", result["stages"])
        self.assertIn("risk_panel_completed", result["stages"])
        self.assertIn("tradingagents_prediction_completed", result["stages"])
        self.assertEqual(result["prediction"]["signal"], "ABSTAIN")
        self.assertTrue(result["prediction"]["not_trade_instruction"])
        self.assertEqual(result["telemetry"]["debate_rounds"], 1)
        self.assertIn("[ledger:snapshot]", result["answer"])


if __name__ == "__main__":
    unittest.main()
