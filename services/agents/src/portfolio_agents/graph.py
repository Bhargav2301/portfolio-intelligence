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
    instrument: str | None
    snapshot: dict[str, Any]
    context: dict[str, Any]
    intent: str
    stages: list[str]
    findings: list[str]
    analyst_reports: dict[str, str]
    perspectives: dict[str, str]
    research_summary: str
    scenario_notes: list[str]
    proposal: dict[str, Any]
    policy: dict[str, Any]
    answer: str
    evidence: list[dict[str, Any]]
    limitations: list[str]
    telemetry: dict[str, Any]


SYSTEM_PROMPT = """You are the synthesis node inside Portfolio Intelligence.
Use only the supplied deterministic portfolio context and analyst summaries.
Never calculate a financial value yourself; quote only supplied values and cite their evidence IDs.
Never promise returns, issue an imperative buy/sell instruction, or claim that an order was placed.
The product is read-only. Missing market, fundamental, news, or sentiment evidence must
stay missing.
Return a concise research summary for a human decision-maker, not hidden reasoning."""


def _append_stage(state: PortfolioAgentState, stage: str) -> list[str]:
    return [*(state.get("stages") or []), stage]


def _holding_for(state: PortfolioAgentState) -> dict[str, Any] | None:
    target = (state.get("instrument") or "").upper()
    holdings = state.get("context", {}).get("ledger", {}).get("holdings") or []
    if target:
        return next(
            (
                item
                for item in holdings
                if str(item.get("instrument_reference", "")).upper() == target
            ),
            None,
        )
    return None


def assemble_context(state: PortfolioAgentState) -> PortfolioAgentState:
    context = state.get("context") or {}
    evidence = list(context.get("evidence") or [])
    return {
        "stages": _append_stage(state, "context_assembled"),
        "evidence": evidence,
        "limitations": list(state.get("snapshot", {}).get("limitations") or []),
        "telemetry": {
            "architecture": "tradingagents-adapted-research-v1",
            "debate_rounds": 1,
            "risk_rounds": 1,
            "external_tool_calls": 0,
        },
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
    return {"stages": _append_stage(state, "data_validated"), "findings": findings}


def route_request(state: PortfolioAgentState) -> PortfolioAgentState:
    question = (state.get("question") or "").lower()
    intent = (
        "security_research"
        if state.get("instrument")
        or any(word in question for word in ("stock", "security", "thesis"))
        else "portfolio_review"
    )
    return {"stages": _append_stage(state, "request_routed"), "intent": intent}


def diagnose_portfolio(state: PortfolioAgentState) -> PortfolioAgentState:
    snapshot = state.get("snapshot") or {}
    rules = snapshot.get("rules") or {}
    monitoring = state.get("context", {}).get("monitoring", {})
    findings = list(state.get("findings") or [])
    metrics = snapshot.get("metrics") or {}
    if metrics.get("current_value") is not None:
        findings.append(
            f"Published portfolio value is INR {metrics['current_value']} [ledger:snapshot]."
        )
    alerts = monitoring.get("alerts") or []
    if alerts:
        findings.append(
            f"Deterministic monitoring reports {len(alerts)} active alert(s) [monitor:snapshot]."
        )
    protected = (rules.get("protected_cash") or {}).get("amount")
    if protected:
        findings.append(f"The configured protected reserve is INR {protected} [rule:portfolio].")
    if rules.get("equal_weighting_allowed") is False:
        findings.append("The active policy prohibits equal-weight allocation [rule:portfolio].")
    return {
        "stages": _append_stage(state, "portfolio_diagnosed"),
        "findings": findings,
    }


def run_asset_analysts(state: PortfolioAgentState) -> PortfolioAgentState:
    if state.get("intent") != "security_research":
        return {
            "stages": _append_stage(state, "asset_research_skipped"),
            "analyst_reports": {},
        }
    instrument = state.get("instrument")
    holding = _holding_for(state)
    if holding:
        market = (
            f"Published position: {holding['quantity']} units at ledger price "
            f"{holding.get('last_price') or 'unavailable'}, weight "
            f"{holding.get('weight_percent') or 'unavailable'}% [ledger:snapshot]."
        )
    else:
        market = (
            f"{instrument or 'The requested security'} is not present in the published holdings; "
            "no position metrics are available."
        )
    reports = {
        "market": market,
        "fundamentals": "No approved point-in-time fundamentals evidence was supplied.",
        "news": "No approved point-in-time news evidence was supplied.",
        "sentiment": "No licensed, point-in-time sentiment evidence was supplied.",
    }
    return {
        "stages": _append_stage(state, "asset_analysts_completed"),
        "analyst_reports": reports,
    }


def run_bull_bear_debate(state: PortfolioAgentState) -> PortfolioAgentState:
    reports = state.get("analyst_reports") or {}
    if not reports:
        return {
            "stages": _append_stage(state, "research_debate_skipped"),
            "perspectives": {},
        }
    holding = _holding_for(state)
    bull = (
        "An upside thesis cannot be supported until current fundamentals and market evidence are "
        "available. Published holding data can define exposure, not expected return."
    )
    bear = (
        "Missing fundamentals, news, and licensed market evidence are material downside "
        "uncertainties; abstention is safer than filling those gaps with model inference."
    )
    if holding and holding.get("unrealized_pnl") is not None:
        bull += (
            f" The ledger records unrealized P/L of INR {holding['unrealized_pnl']} "
            "[ledger:snapshot], which is historical context rather than a forecast."
        )
    return {
        "stages": _append_stage(state, "research_debate_completed"),
        "perspectives": {"bull": bull, "bear": bear},
    }


def synthesize_research(state: PortfolioAgentState) -> PortfolioAgentState:
    settings = get_agent_settings()
    if not settings.live_model_enabled:
        return {
            "stages": _append_stage(state, "model_synthesis_skipped"),
            "research_summary": (
                "The analyst panel ran in deterministic safe mode. Live synthesis is disabled, "
                "and evidence gaps were preserved rather than guessed."
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
        "analyst_reports": state.get("analyst_reports"),
        "perspectives": state.get("perspectives"),
        "evidence_ids": [item.get("id") for item in state.get("evidence") or []],
    }
    response = model.invoke(
        [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=f"Synthesize this supplied context only:\n{supplied!r}"),
        ]
    )
    telemetry = dict(state.get("telemetry") or {})
    telemetry["model_calls"] = 1
    return {
        "stages": _append_stage(state, "model_synthesis_completed"),
        "research_summary": safe_response_text(str(response.content)),
        "telemetry": telemetry,
    }


def plan_scenario(state: PortfolioAgentState) -> PortfolioAgentState:
    snapshot = state.get("snapshot") or {}
    monitoring = state.get("context", {}).get("monitoring", {})
    alerts = monitoring.get("alerts") or []
    concentration = [item for item in alerts if item.get("kind") == "concentration"]
    if snapshot.get("quality_state") != "trusted":
        notes = [
            "Reconcile and publish the portfolio before comparing allocation-change scenarios.",
            "A no-action decision is valid while the source data is incomplete.",
        ]
        proposal_type = "data_review"
        title = "Complete portfolio reconciliation"
        candidate_actions: list[dict[str, str]] = []
    elif concentration:
        notes = [
            "Compare the current allocation with a concentration-reduction scenario.",
            "Keep protected reserve and the no-equal-weight rule unchanged.",
        ]
        proposal_type = "rebalance_review"
        title = "Review concentration before the next weekly decision"
        candidate_actions = [
            {
                "action": "review_reduction_scenario",
                "instrument_reference": str(item.get("instrument_reference")),
                "reason": f"Published weight {item.get('observed_value')}% exceeds the "
                f"{item.get('threshold_value')}% rule [monitor:snapshot].",
            }
            for item in concentration
        ]
    else:
        notes = [
            "No allocation breach is present in the current deterministic monitor snapshot.",
            "Retaining the current portfolio is an explicit scenario, not inactivity by default.",
        ]
        proposal_type = "no_action_review"
        title = "Review a no-action scenario"
        candidate_actions = []
    proposal = {
        "type": proposal_type,
        "status": "proposal_only",
        "title": title,
        "candidate_actions": candidate_actions,
        "constraints": ["protected_cash", "no_equal_weighting", "human_decision_required"],
        "can_execute": False,
    }
    return {
        "stages": _append_stage(state, "scenario_checked"),
        "scenario_notes": notes,
        "proposal": proposal,
    }


def run_risk_panel(state: PortfolioAgentState) -> PortfolioAgentState:
    proposal = state.get("proposal") or {}
    monitoring = state.get("context", {}).get("monitoring", {})
    alerts = monitoring.get("alerts") or []
    perspectives = dict(state.get("perspectives") or {})
    perspectives.update(
        {
            "aggressive_risk": "Opportunity review is allowed only after evidence gaps close.",
            "neutral_risk": (
                f"The proposal is {proposal.get('status', 'unavailable')} and has no "
                "execution capability."
            ),
            "conservative_risk": (
                "Block allocation suggestions while a critical monitor alert exists."
                if any(item.get("severity") == "critical" for item in alerts)
                else "Preserve hard constraints and require a human decision."
            ),
        }
    )
    return {
        "stages": _append_stage(state, "risk_panel_completed"),
        "perspectives": perspectives,
    }


def apply_policy_gate(state: PortfolioAgentState) -> PortfolioAgentState:
    decision = evaluate_request(state.get("question") or "", state.get("snapshot") or {})
    limitations = list(dict.fromkeys([*(state.get("limitations") or []), *decision.limitations]))
    proposal = dict(state.get("proposal") or {})
    if decision.decision != "allow_analysis":
        proposal["status"] = (
            "suppressed" if decision.decision == "suppress_execution" else "limited"
        )
        proposal["candidate_actions"] = []
    return {
        "stages": _append_stage(state, "policy_checked"),
        "policy": {"decision": decision.decision, "reasons": list(decision.reasons)},
        "limitations": limitations,
        "proposal": proposal,
    }


def compose_response(state: PortfolioAgentState) -> PortfolioAgentState:
    policy = state.get("policy") or {}
    findings = state.get("findings") or []
    notes = state.get("scenario_notes") or []
    synthesis = state.get("research_summary") or ""
    proposal = state.get("proposal") or {}
    if policy.get("decision") == "suppress_execution":
        opening = (
            "Portfolio Intelligence cannot place or execute an order. It can inspect a "
            "read-only scenario after the portfolio is reconciled."
        )
    elif policy.get("decision") == "limited":
        opening = (
            "The portfolio is not yet trusted enough for an investment-change proposal. "
            "Review and publish the source data first."
        )
    else:
        opening = "The published portfolio data passed the current analysis gate [ledger:snapshot]."
    sections = [opening]
    if findings:
        sections.append("Findings:\n- " + "\n- ".join(findings))
    if synthesis:
        sections.append("Research panel:\n" + synthesis)
    if proposal.get("title"):
        sections.append(f"Proposal for review:\n- {proposal['title']}")
    if notes:
        sections.append("Next review:\n- " + "\n- ".join(notes))
    sections.append("No trade was placed. You remain the decision-maker.")
    return {
        "stages": _append_stage(state, "response_composed"),
        "answer": safe_response_text("\n\n".join(sections)),
    }


def build_graph(settings: AgentSettings | None = None, checkpointer=None):
    del settings
    builder = StateGraph(PortfolioAgentState)
    builder.add_node("assemble_context", assemble_context)
    builder.add_node("validate_data", validate_data)
    builder.add_node("route_request", route_request)
    builder.add_node("diagnose_portfolio", diagnose_portfolio)
    builder.add_node("run_asset_analysts", run_asset_analysts)
    builder.add_node("run_bull_bear_debate", run_bull_bear_debate)
    builder.add_node("synthesize_research", synthesize_research)
    builder.add_node("plan_scenario", plan_scenario)
    builder.add_node("run_risk_panel", run_risk_panel)
    builder.add_node("apply_policy_gate", apply_policy_gate)
    builder.add_node("compose_response", compose_response)
    builder.add_edge(START, "assemble_context")
    builder.add_edge("assemble_context", "validate_data")
    builder.add_edge("validate_data", "route_request")
    builder.add_edge("route_request", "diagnose_portfolio")
    builder.add_edge("diagnose_portfolio", "run_asset_analysts")
    builder.add_edge("run_asset_analysts", "run_bull_bear_debate")
    builder.add_edge("run_bull_bear_debate", "synthesize_research")
    builder.add_edge("synthesize_research", "plan_scenario")
    builder.add_edge("plan_scenario", "run_risk_panel")
    builder.add_edge("run_risk_panel", "apply_policy_gate")
    builder.add_edge("apply_policy_gate", "compose_response")
    builder.add_edge("compose_response", END)
    return builder.compile(checkpointer=checkpointer or InMemorySaver())


graph = build_graph()
