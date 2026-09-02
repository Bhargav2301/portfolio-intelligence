from datetime import date, datetime, timezone

import pytest
from pi_agent_runtime.models import AnalysisRunRequest, HoldingSnapshot, SymbolResult
from pi_agent_runtime.workflow import LangGraphPortfolioWorkflow

pytest.importorskip("langgraph")


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


class FailingSmallCapEngine:
    def analyze(self, request, holding, report):
        raise RuntimeError("provider returned no supported market data")


def test_langgraph_routes_analysis_through_policy_review() -> None:
    request = AnalysisRunRequest(
        portfolio_id="portfolio-1",
        snapshot_id="snapshot-123",
        snapshot_hash="c" * 64,
        as_of=datetime.now(timezone.utc),  # noqa: UP017 - Python 3.10 runtime
        analysis_date=date.today(),
        holdings=[
            HoldingSnapshot(
                symbol="EXMPL",
                name="Example Industries",
                exchange="NSE",
                analysis_symbol="EXMPL.NS",
                quantity=1,
                average_cost=100,
                current_price=110,
                market_value=110,
                allocation_percent=100,
                price_as_of=datetime.now(
                    timezone.utc  # noqa: UP017 - Python 3.10 runtime
                ),
            )
        ],
    )
    events = []
    persisted = []
    workflow = LangGraphPortfolioWorkflow(
        FakeEngine(),
        lambda stage, message, symbol=None: events.append((stage, message, symbol)),
        persisted.append,
    )

    results = workflow.invoke(request, ["EXMPL"])

    assert [result.symbol for result in results] == ["EXMPL"]
    assert [result.symbol for result in persisted] == ["EXMPL"]
    assert any(check.code == "position_cap" for check in results[0].policy_checks)
    assert events[0] == ("symbol", "Analysis started", "EXMPL")


def test_langgraph_records_abstention_when_one_symbol_upstream_fails() -> None:
    request = AnalysisRunRequest(
        portfolio_id="portfolio-1",
        snapshot_id="snapshot-123",
        snapshot_hash="d" * 64,
        as_of=datetime.now(timezone.utc),  # noqa: UP017 - Python 3.10 runtime
        analysis_date=date.today(),
        holdings=[
            HoldingSnapshot(
                symbol="SMALLCAP",
                name="Small Cap Example",
                exchange="BSE",
                analysis_symbol="SMALLCAP.BO",
                quantity=1,
                average_cost=100,
                current_price=110,
                market_value=110,
                allocation_percent=100,
                price_as_of=datetime.now(
                    timezone.utc  # noqa: UP017 - Python 3.10 runtime
                ),
            )
        ],
    )
    events = []
    persisted = []
    workflow = LangGraphPortfolioWorkflow(
        FailingSmallCapEngine(),
        lambda stage, message, symbol=None: events.append((stage, message, symbol)),
        persisted.append,
    )

    results = workflow.invoke(request, ["SMALLCAP"])

    assert results[0].rating == "Unknown"
    assert results[0].trader_action == "Unknown"
    assert persisted[0].symbol == "SMALLCAP"
    assert any(stage == "fallback" for stage, _message, _symbol in events)
