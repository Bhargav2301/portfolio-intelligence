from __future__ import annotations

import asyncio
import os
import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
os.environ.pop("OPENAI_API_KEY", None)
os.environ.pop("OPENAI_MODEL", None)

from portfolio_agents.graph import graph


class AgentGraphTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
