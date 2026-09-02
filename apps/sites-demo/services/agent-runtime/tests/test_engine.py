from datetime import datetime, timezone

from pi_agent_runtime.engine import TradingAgentsEngine
from pi_agent_runtime.models import HoldingSnapshot


def holding() -> HoldingSnapshot:
    return HoldingSnapshot(
        symbol="LT",
        name="Larsen & Toubro",
        exchange="NSE",
        analysis_symbol="LT.NS",
        quantity=1,
        average_cost=3000,
        current_price=3500,
        market_value=3500,
        allocation_percent=10,
        price_as_of=datetime.now(timezone.utc),
    )


def test_to_result_parses_rendered_upstream_markdown() -> None:
    state = {
        "final_trade_decision": """**Rating**: Overweight

**Executive Summary**: Add exposure gradually while monitoring execution risk.

**Investment Thesis**: The analyst evidence supports durable order-book growth.

**Time Horizon**: 6-12 months""",
        "trader_investment_plan": """**Action**: Buy

**Reasoning**: The research plan supports a measured increase.

FINAL TRANSACTION PROPOSAL: **BUY**""",
        "investment_debate_state": {"judge_decision": "Constructive research view"},
        "risk_debate_state": {"judge_decision": "Size within portfolio limits"},
        "market_report": "Market report",
        "sentiment_report": "Sentiment report",
        "news_report": "News report",
        "fundamentals_report": "Fundamentals report",
    }

    result = TradingAgentsEngine._to_result(holding(), state, "Overweight")

    assert result.rating == "Overweight"
    assert result.executive_summary == (
        "Add exposure gradually while monitoring execution risk."
    )
    assert result.investment_thesis == (
        "The analyst evidence supports durable order-book growth."
    )
    assert result.trader_action == "Buy"
    assert result.trader_reasoning == (
        "The research plan supports a measured increase."
    )


def test_to_result_keeps_object_shaped_adapter_compatibility() -> None:
    state = {
        "trader_investment_plan": {
            "action": "Hold",
            "reasoning": "Wait for the next filing.",
        },
        "investment_debate_state": {},
        "risk_debate_state": {},
    }
    decision = {
        "rating": "Hold",
        "executive_summary": "Maintain the current position.",
        "investment_thesis": "Evidence is balanced.",
    }

    result = TradingAgentsEngine._to_result(holding(), state, decision)

    assert result.rating == "Hold"
    assert result.executive_summary == "Maintain the current position."
    assert result.investment_thesis == "Evidence is balanced."
    assert result.trader_action == "Hold"
    assert result.trader_reasoning == "Wait for the next filing."
