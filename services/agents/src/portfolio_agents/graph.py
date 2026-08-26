from __future__ import annotations

from typing import Any, TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from portfolio_agents.policy import evaluate_request, safe_response_text
from portfolio_agents.settings import AgentSettings, get_agent_settings


class PortfolioAgentState(TypedDict, total=False):
    run_id: str
    tenant_id: str
    portfolio_id: str
    as_of: str
    question: str
    snapshot: dict[str, Any]
    stages: list[str]
    findings: list[str]
    research_summary: str
    scenario_notes: list[str]
    policy: dict[str, Any]
    answer: str
    evidence: list[dict[str, Any]]
    limitations: list[str]


SYSTEM_PROMPT = """You are the explanation node inside Portfolio Intelligence.
Use only the supplied portfolio snapshot and limitations.
Never calculate a financial value yourself; quote only supplied metric values.
Never promise returns, issue an imperative buy/sell instruction, or claim that an order was placed.
The product is read-only. State missing evidence plainly.
Return a concise explanation for a human decision-maker."""


def _append_stage(state: PortfolioAgentState, stage: str) -> list[str]:
    return [*(state.get("stages") or []), stage]


def assemble_context(state: PortfolioAgentState) -> PortfolioAgentState:
    return {
        "stages": _append_stage(state, "context_assembled"),
        "evidence": state.get("evidence") or [],
        "limitations": list(state.get("snapshot", {}).get("limitations") or []),
    }


def validate_data(state: PortfolioAgentState) -> PortfolioAgentState:
    snapshot = state.get("snapshot") or {}
    findings: list[str] = []
    if snapshot.get("quality_state") != "trusted":
        findings.append("The portfolio does not yet have a trusted published ledger.")
    metrics = snapshot.get("metrics") or {}
    missing = sorted(key for key, value in metrics.items() if value is None)
    if missing:
        findings.append("Unavailable metrics: " + ", ".join(missing) + ".")
    return {
        "stages": _append_stage(state, "data_validated"),
        "findings": findings,
    }


def diagnose_portfolio(state: PortfolioAgentState) -> PortfolioAgentState:
    snapshot = state.get("snapshot") or {}
    rules = snapshot.get("rules") or {}
    findings = list(state.get("findings") or [])
    protected = (rules.get("protected_cash") or {}).get("amount")
    if protected:
        findings.append(f"The configured protected reserve is INR {protected}.")
    if rules.get("equal_weighting_allowed") is False:
        findings.append("The active policy prohibits equal-weight allocation.")
    return {
        "stages": _append_stage(state, "portfolio_diagnosed"),
        "findings": findings,
    }


def synthesize_research(state: PortfolioAgentState) -> PortfolioAgentState:
    settings = get_agent_settings()
    if not settings.live_model_enabled:
        return {
            "stages": _append_stage(state, "model_synthesis_skipped"),
            "research_summary": (
                "Live model synthesis is disabled. Add an approved model and API key to enable it."
            ),
        }
    model = ChatOpenAI(
        api_key=settings.openai_api_key,
        model=settings.openai_model,
        temperature=0,
        timeout=settings.agent_timeout_seconds,
        max_retries=1,
    )
    supplied = {
        "question": state.get("question"),
        "snapshot": state.get("snapshot"),
        "findings": state.get("findings"),
    }
    response = model.invoke(
        [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=f"Explain this supplied context only:\n{supplied!r}"),
        ]
    )
    return {
        "stages": _append_stage(state, "model_synthesis_completed"),
        "research_summary": safe_response_text(str(response.content)),
    }


def plan_scenario(state: PortfolioAgentState) -> PortfolioAgentState:
    snapshot = state.get("snapshot") or {}
    if snapshot.get("quality_state") != "trusted":
        notes = [
            "Reconcile and publish the portfolio before comparing allocation-change scenarios.",
            "A no-action decision is valid while the source data is incomplete.",
        ]
    else:
        notes = [
            "Compare any proposal against the current portfolio, benchmark, and downside case.",
            "Keep protected reserve and active allocation rules unchanged.",
        ]
    return {
        "stages": _append_stage(state, "scenario_checked"),
        "scenario_notes": notes,
    }


def apply_policy_gate(state: PortfolioAgentState) -> PortfolioAgentState:
    decision = evaluate_request(state.get("question") or "", state.get("snapshot") or {})
    limitations = list(dict.fromkeys([*(state.get("limitations") or []), *decision.limitations]))
    return {
        "stages": _append_stage(state, "policy_checked"),
        "policy": {
            "decision": decision.decision,
            "reasons": list(decision.reasons),
        },
        "limitations": limitations,
    }


def compose_response(state: PortfolioAgentState) -> PortfolioAgentState:
    policy = state.get("policy") or {}
    findings = state.get("findings") or []
    notes = state.get("scenario_notes") or []
    synthesis = state.get("research_summary") or ""
    if policy.get("decision") == "suppress_execution":
        opening = (
            "Portfolio Intelligence cannot place or execute an order. "
            "It can help you inspect a read-only scenario after the portfolio is reconciled."
        )
    elif policy.get("decision") == "limited":
        opening = (
            "The portfolio is not yet trusted enough for an investment-change proposal. "
            "The correct next step is to review and publish the source data."
        )
    else:
        opening = "The portfolio data passed the current analysis gate."
    sections = [opening]
    if findings:
        sections.append("Findings:\n- " + "\n- ".join(findings))
    if synthesis:
        sections.append("AI explanation:\n" + synthesis)
    if notes:
        sections.append("Next review:\n- " + "\n- ".join(notes))
    sections.append("No trade was placed. You remain the decision-maker.")
    return {
        "stages": _append_stage(state, "response_composed"),
        "answer": safe_response_text("\n\n".join(sections)),
    }


def build_graph(settings: AgentSettings | None = None):
    del settings
    builder = StateGraph(PortfolioAgentState)
    builder.add_node("assemble_context", assemble_context)
    builder.add_node("validate_data", validate_data)
    builder.add_node("diagnose_portfolio", diagnose_portfolio)
    builder.add_node("synthesize_research", synthesize_research)
    builder.add_node("plan_scenario", plan_scenario)
    builder.add_node("apply_policy_gate", apply_policy_gate)
    builder.add_node("compose_response", compose_response)
    builder.add_edge(START, "assemble_context")
    builder.add_edge("assemble_context", "validate_data")
    builder.add_edge("validate_data", "diagnose_portfolio")
    builder.add_edge("diagnose_portfolio", "synthesize_research")
    builder.add_edge("synthesize_research", "plan_scenario")
    builder.add_edge("plan_scenario", "apply_policy_gate")
    builder.add_edge("apply_policy_gate", "compose_response")
    builder.add_edge("compose_response", END)
    return builder.compile(checkpointer=InMemorySaver())


graph = build_graph()

