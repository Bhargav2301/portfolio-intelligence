from __future__ import annotations

from collections.abc import Callable
from typing import TypedDict

from .engine import AnalysisEngine, EventReporter
from .models import AnalysisRunRequest, HoldingSnapshot, SymbolResult
from .policy import result_policy_checks

ResultReporter = Callable[[SymbolResult], None]


class PortfolioWorkflowState(TypedDict):
    request: AnalysisRunRequest
    holdings: dict[str, HoldingSnapshot]
    selected_symbols: list[str]
    cursor: int
    current_symbol: str | None
    pending_result: SymbolResult | None
    results: list[SymbolResult]


class LangGraphPortfolioWorkflow:
    """Portfolio-level graph surrounding TradingAgents' ticker-level graph.

    Deterministic validation happens before this graph. Each symbol is then
    analyzed by TradingAgents, independently policy-reviewed, and persisted by
    callbacks. Keeping this as an explicit StateGraph gives future PI modes one
    inspectable routing contract without modifying TradingAgents internals.
    """

    engine_name = "langgraph"
    workflow_version = "pi-portfolio-v1"

    def __init__(
        self,
        engine: AnalysisEngine,
        report_event: EventReporter,
        report_result: ResultReporter,
    ) -> None:
        self._engine = engine
        self._report_event = report_event
        self._report_result = report_result
        self._graph = self._compile()

    def _compile(self):
        from langgraph.graph import END, START, StateGraph

        graph = StateGraph(PortfolioWorkflowState)
        graph.add_node("select_symbol", self._select_symbol)
        graph.add_node("tradingagents_analysis", self._analyze_symbol)
        graph.add_node("pi_policy_review", self._apply_policy)
        graph.add_edge(START, "select_symbol")
        graph.add_edge("select_symbol", "tradingagents_analysis")
        graph.add_edge("tradingagents_analysis", "pi_policy_review")
        graph.add_conditional_edges(
            "pi_policy_review",
            self._route_after_policy,
            {"next_symbol": "select_symbol", "complete": END},
        )
        return graph.compile()

    def invoke(self, request: AnalysisRunRequest, selected_symbols: list[str]) -> list[SymbolResult]:
        final_state = self._graph.invoke({
            "request": request,
            "holdings": {holding.symbol: holding for holding in request.holdings},
            "selected_symbols": selected_symbols,
            "cursor": 0,
            "current_symbol": None,
            "pending_result": None,
            "results": [],
        })
        return list(final_state["results"])

    def _select_symbol(self, state: PortfolioWorkflowState) -> dict[str, object]:
        symbol = state["selected_symbols"][state["cursor"]]
        self._report_event("symbol", "Analysis started", symbol)
        return {"current_symbol": symbol, "pending_result": None}

    def _analyze_symbol(self, state: PortfolioWorkflowState) -> dict[str, object]:
        symbol = state["current_symbol"]
        if not symbol:
            raise RuntimeError("LangGraph workflow reached analysis without a selected symbol")
        holding = state["holdings"][symbol]
        result = self._engine.analyze(state["request"], holding, self._report_event)
        return {"pending_result": result}

    def _apply_policy(self, state: PortfolioWorkflowState) -> dict[str, object]:
        symbol = state["current_symbol"]
        result = state["pending_result"]
        if not symbol or result is None:
            raise RuntimeError("LangGraph workflow reached policy review without an analysis result")
        result.policy_checks = result_policy_checks(state["request"], state["holdings"][symbol], result)
        self._report_result(result)
        self._report_event("symbol", "Analysis completed", symbol)
        return {
            "results": [*state["results"], result],
            "cursor": state["cursor"] + 1,
            "pending_result": None,
        }

    @staticmethod
    def _route_after_policy(state: PortfolioWorkflowState) -> str:
        return "next_symbol" if state["cursor"] < len(state["selected_symbols"]) else "complete"

