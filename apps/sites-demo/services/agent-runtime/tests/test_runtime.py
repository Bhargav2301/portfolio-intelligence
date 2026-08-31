from datetime import date, datetime, timezone

from pi_agent_runtime.models import AnalysisRunRequest, HoldingSnapshot, SymbolResult
from pi_agent_runtime.orchestration import RunCoordinator
from pi_agent_runtime.store import InMemoryRunStore


class FakeEngine:
    def analyze(self, request, holding, report):
        report("analysts", "Synthetic test completed", holding.symbol)
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


class FakeWorkflow:
    def __init__(self, engine, report_event, report_result):
        self.engine = engine
        self.report_event = report_event
        self.report_result = report_result

    def invoke(self, request, selected_symbols):
        holdings = {holding.symbol: holding for holding in request.holdings}
        results = []
        for symbol in selected_symbols:
            self.report_event("symbol", "Analysis started", symbol)
            result = self.engine.analyze(request, holdings[symbol], self.report_event)
            self.report_result(result)
            results.append(result)
        return results


def build_request() -> AnalysisRunRequest:
    return AnalysisRunRequest(
        portfolio_id="portfolio-1",
        snapshot_id="snapshot-123",
        snapshot_hash="b" * 64,
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


def test_coordinator_completes_with_fake_engine() -> None:
    import asyncio

    coordinator = RunCoordinator(
        store=InMemoryRunStore(),
        engine=FakeEngine(),
        workflow_factory=FakeWorkflow,
    )
    request = build_request()
    run = coordinator.create("owner@example.com", request)
    asyncio.run(coordinator.execute(run.id, request))
    completed = coordinator.store.get(run.id)
    assert completed is not None
    assert completed.status == "completed"
    assert completed.results[0].rating == "Hold"
    assert completed.workflow_engine == "langgraph"
    assert coordinator.store.events(run.id)
