from datetime import date, datetime, timezone

import pytest

pytest.importorskip("langgraph")

from pi_agent_runtime.models import AnalysisRunRequest, HoldingSnapshot, SymbolResult
from pi_agent_runtime.workflow import LangGraphPortfolioWorkflow


class FakeEngine:
    def analyze(self, request, holding, report):
        report("tradingagents", "Ticker graph completed", holding.symbol)
        return SymbolResult(
            symbol=holding.symbol,
            analysis_symbol=holding.analysis_symbol,
            rating="Hold",
            executive_summary="Stable",
            investment_thesis="Test thesis",
            trader_action="Hold",
            trader_reasoning="No change",
            research_judgement="Balanced",
            risk_judgement="Within limits",
            policy_checks=[],
            reports={"market": "Test"},
        )


def test_langgraph_routes_analysis_through_policy_review() -> None:
    request = AnalysisRunRequest(
        portfolio_id="portfolio-1",
        snapshot_id="snapshot-123",
        snapshot_hash="c" * 64,
        as_of=datetime.now(timezone.utc),
        analysis_date=date.today(),
        holdings=[HoldingSnapshot(
            symbol="INFY",
            name="Infosys",
            exchange="NSE",
            analysis_symbol="INFY.NS",
            quantity=1,
            average_cost=100,
            current_price=110,
            market_value=110,
            allocation_percent=100,
            price_as_of=datetime.now(timezone.utc),
        )],
    )
    events = []
    persisted = []
    workflow = LangGraphPortfolioWorkflow(
        FakeEngine(),
        lambda stage, message, symbol=None: events.append((stage, message, symbol)),
        persisted.append,
    )

    results = workflow.invoke(request, ["INFY"])

    assert [result.symbol for result in results] == ["INFY"]
    assert [result.symbol for result in persisted] == ["INFY"]
    assert any(check.code == "position_cap" for check in results[0].policy_checks)
    assert events[0] == ("symbol", "Analysis started", "INFY")
