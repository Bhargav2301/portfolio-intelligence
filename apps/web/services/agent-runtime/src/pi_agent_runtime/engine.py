from __future__ import annotations

import json
import os
from collections.abc import Callable
from pathlib import Path
from threading import Lock
from typing import Any, Protocol

from .models import AnalysisRunRequest, HoldingSnapshot, SymbolResult

EventReporter = Callable[[str, str, str | None], None]


class AnalysisEngine(Protocol):
    def analyze(
        self,
        request: AnalysisRunRequest,
        holding: HoldingSnapshot,
        report: EventReporter,
    ) -> SymbolResult: ...


class TradingAgentsEngine:
    """Thin adapter. The lock protects TradingAgents' process-global configuration."""

    def __init__(self) -> None:
        self._lock = Lock()

    def analyze(
        self,
        request: AnalysisRunRequest,
        holding: HoldingSnapshot,
        report: EventReporter,
    ) -> SymbolResult:
        with self._lock:
            return self._analyze_locked(request, holding, report)

    def _analyze_locked(
        self,
        request: AnalysisRunRequest,
        holding: HoldingSnapshot,
        report: EventReporter,
    ) -> SymbolResult:
        try:
            from langchain_core.callbacks import BaseCallbackHandler
            from tradingagents.default_config import DEFAULT_CONFIG
            from tradingagents.graph.trading_graph import TradingAgentsGraph
        except ImportError as error:
            raise RuntimeError(
                "TradingAgents dependencies are not installed"
            ) from error

        class SanitizedCallback(BaseCallbackHandler):
            def on_llm_start(
                self,
                serialized: dict[str, Any],
                prompts: list[str],
                **kwargs: Any,
            ) -> None:
                name = serialized.get("name") or serialized.get(
                    "id", ["language model"]
                )[-1]
                report("model", f"{name} started", holding.symbol)

            def on_llm_end(self, response: Any, **kwargs: Any) -> None:
                report("model", "Model response completed", holding.symbol)

            def on_tool_start(
                self,
                serialized: dict[str, Any],
                input_str: str,
                **kwargs: Any,
            ) -> None:
                name = serialized.get("name", "market data tool")
                report("tool", f"{name} started", holding.symbol)

            def on_tool_end(self, output: Any, **kwargs: Any) -> None:
                report("tool", "Tool lookup completed", holding.symbol)

            def on_tool_error(self, error: BaseException, **kwargs: Any) -> None:
                report(
                    "tool",
                    f"Tool lookup failed: {type(error).__name__}",
                    holding.symbol,
                )

        config = dict(DEFAULT_CONFIG)
        config.update(self._environment_config(request))
        report(
            "analysts",
            "Market, social, news, and fundamentals review started",
            holding.symbol,
        )
        graph = TradingAgentsGraph(
            selected_analysts=list(request.selected_analysts),
            debug=False,
            config=config,
            callbacks=[SanitizedCallback()],
        )
        final_state, decision = graph.propagate(
            holding.analysis_symbol,
            request.analysis_date.isoformat(),
            asset_type="stock",
        )
        report(
            "decision",
            "Research, trading, risk, and portfolio decisions completed",
            holding.symbol,
        )
        return self._to_result(holding, final_state or {}, decision)

    def _environment_config(self, request: AnalysisRunRequest) -> dict[str, Any]:
        result_dir = Path(
            os.getenv("TRADINGAGENTS_RESULTS_DIR", "/tmp/pi-tradingagents")
        )
        result_dir.mkdir(parents=True, exist_ok=True)
        config: dict[str, Any] = {
            "results_dir": str(result_dir),
            "max_debate_rounds": int(os.getenv("TA_MAX_DEBATE_ROUNDS", "1")),
            "max_risk_discuss_rounds": int(os.getenv("TA_MAX_RISK_ROUNDS", "1")),
            "online_tools": os.getenv("TA_ONLINE_TOOLS", "true").lower() == "true",
        }
        mapping = {
            "TA_LLM_PROVIDER": "llm_provider",
            "TA_DEEP_THINK_LLM": "deep_think_llm",
            "TA_QUICK_THINK_LLM": "quick_think_llm",
            "TA_BACKEND_URL": "backend_url",
        }
        for environment_name, key in mapping.items():
            if value := os.getenv(environment_name):
                config[key] = value
        if raw := os.getenv("TA_CONFIG_JSON"):
            config.update(json.loads(raw))
        return config

    @staticmethod
    def _text(value: Any, fallback: str) -> str:
        if isinstance(value, str) and value.strip():
            return value.strip()[:12000]
        return fallback

    @classmethod
    def _decision_field(cls, decision: Any, key: str, fallback: str) -> str:
        if isinstance(decision, dict):
            return cls._text(decision.get(key), fallback)
        return cls._text(getattr(decision, key, None), fallback)

    @classmethod
    def _to_result(
        cls,
        holding: HoldingSnapshot,
        state: dict[str, Any],
        decision: Any,
    ) -> SymbolResult:
        rating = cls._decision_field(decision, "rating", "Unknown")
        allowed_ratings = {"Buy", "Overweight", "Hold", "Underweight", "Sell"}
        if rating not in allowed_ratings:
            rating = "Unknown"

        trader_plan = state.get("trader_investment_plan") or {}
        trader_action = cls._decision_field(trader_plan, "action", "Unknown")
        if trader_action not in {"Buy", "Hold", "Sell"}:
            trader_action = "Unknown"

        return SymbolResult(
            symbol=holding.symbol,
            analysis_symbol=holding.analysis_symbol or holding.symbol,
            rating=rating,
            executive_summary=cls._decision_field(
                decision,
                "executive_summary",
                "No executive summary was returned.",
            ),
            investment_thesis=cls._decision_field(
                decision,
                "investment_thesis",
                "No investment thesis was returned.",
            ),
            trader_action=trader_action,
            trader_reasoning=cls._decision_field(
                trader_plan,
                "reasoning",
                "No trader summary was returned.",
            ),
            research_judgement=cls._text(
                (state.get("investment_debate_state") or {}).get("judge_decision"),
                "No research-manager summary was returned.",
            ),
            risk_judgement=cls._text(
                (state.get("risk_debate_state") or {}).get("judge_decision"),
                "No risk-manager summary was returned.",
            ),
            policy_checks=[],
            reports={
                "market": cls._text(state.get("market_report"), "Not returned"),
                "sentiment": cls._text(state.get("sentiment_report"), "Not returned"),
                "news": cls._text(state.get("news_report"), "Not returned"),
                "fundamentals": cls._text(
                    state.get("fundamentals_report"), "Not returned"
                ),
            },
        )
