from datetime import date, datetime, timezone

from pi_agent_runtime.models import (
    AnalysisRunRequest,
    HoldingSnapshot,
    PortfolioPolicy,
    SymbolResult,
)
from pi_agent_runtime.policy import is_blocked, readiness_checks, result_policy_checks


def request_for(analysis_symbol: str | None = "EXMPL.NS") -> AnalysisRunRequest:
    return AnalysisRunRequest(
        portfolio_id="portfolio-1",
        snapshot_id="snapshot-123",
        snapshot_hash="a" * 64,
        as_of=datetime.now(timezone.utc),  # noqa: UP017 - Python 3.10 runtime
        analysis_date=date.today(),
        holdings=[
            HoldingSnapshot(
                symbol="EXMPL",
                name="Example Industries",
                exchange="NSE",
                analysis_symbol=analysis_symbol,
                quantity=10,
                average_cost=1000,
                current_price=1200,
                market_value=12000,
                allocation_percent=100,
                price_as_of=datetime.now(
                    timezone.utc  # noqa: UP017 - Python 3.10 runtime
                ),
            )
        ],
        selected_symbols=["EXMPL"],
        policy=PortfolioPolicy(max_position_weight_percent=20),
    )


def test_missing_mapping_blocks_run() -> None:
    checks = readiness_checks(request_for(None))
    assert is_blocked(checks)
    assert any(check.code == "instrument_mapping_missing" for check in checks)


def test_buy_over_cap_is_blocked() -> None:
    request = request_for()
    holding = request.holdings[0]
    result = SymbolResult(
        symbol="EXMPL",
        analysis_symbol="EXMPL.NS",
        rating="Buy",
        executive_summary="Summary",
        investment_thesis="Thesis",
        trader_action="Buy",
        trader_reasoning="Reason",
        research_judgement="Research",
        risk_judgement="Risk",
        policy_checks=[],
        reports={},
    )
    checks = result_policy_checks(request, holding, result)
    assert any(
        check.code == "position_cap" and check.severity == "block" for check in checks
    )
