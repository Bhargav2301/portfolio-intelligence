"use client";

import { useEffect, useMemo, useState } from "react";
import type { AgentRun, AgentRunEvent, AgentRuntimeStatus, DashboardData } from "../lib/types";

const inr = new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 });
const terminalStatuses = new Set(["completed", "blocked", "failed"]);

export function AgentDesk({ data, onRunChange }: { data: DashboardData; onRunChange: (runId: string | null) => void }) {
  const eligibleSymbols = useMemo(
    () => data.positions.filter((position) => position.mappingStatus === "confirmed").map((position) => position.symbol),
    [data.positions],
  );
  const [runtime, setRuntime] = useState<AgentRuntimeStatus | null>(null);
  const [selected, setSelected] = useState<string[]>(eligibleSymbols);
  const [run, setRun] = useState<AgentRun | null>(null);
  const [events, setEvents] = useState<AgentRunEvent[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const unresolved = data.positions.filter((position) => position.mappingStatus !== "confirmed");
  const allocationTotal = data.positions.reduce((sum, position) => sum + position.allocationPercent, 0);
  const runId = run?.id;
  const runStatus = run?.status;
  const afterSequence = events.at(-1)?.sequence ?? 0;
  const localChecks = [
    { label: "Portfolio truth", pass: allocationTotal >= 99 && allocationTotal <= 101, detail: `${allocationTotal.toFixed(2)}% reconciled` },
    { label: "Instrument mapping", pass: unresolved.length === 0, detail: unresolved.length ? `${unresolved.length} unresolved` : `${eligibleSymbols.length} confirmed` },
    { label: "Price timestamp", pass: Boolean(Date.parse(data.asOf)), detail: `Runtime enforces ${Math.round(data.agentPolicy.dataMaxAgeMinutes / 60)}h max age` },
    { label: "Execution control", pass: true, detail: "Human confirmation required" },
  ];
  const ready = Boolean(runtime?.reachable) && localChecks.every((check) => check.pass) && selected.length > 0 && !data.portfolio.isDemo;

  useEffect(() => {
    fetch("/api/agents/status", { cache: "no-store" })
      .then((response) => response.json())
      .then((payload: AgentRuntimeStatus) => setRuntime(payload))
      .catch(() => setRuntime({ configured: false, reachable: false, runtime: "tradingagents", version: null, detail: "Runtime status could not be checked." }));
  }, []);

  useEffect(() => {
    if (!runId || !runStatus || terminalStatuses.has(runStatus)) return;
    let active = true;
    const poll = async () => {
      try {
        const [runResponse, eventResponse] = await Promise.all([
          fetch(`/api/agents/runs/${encodeURIComponent(runId)}`, { cache: "no-store" }),
          fetch(`/api/agents/runs/${encodeURIComponent(runId)}/events?after=${afterSequence}`, { cache: "no-store" }),
        ]);
        const nextRun = await runResponse.json() as AgentRun & { error?: string };
        const eventPayload = await eventResponse.json() as { events?: AgentRunEvent[] };
        if (!runResponse.ok) throw new Error(nextRun.error ?? "Run status unavailable");
        if (active) {
          setRun(nextRun);
          setEvents((current) => [...current, ...(eventPayload.events ?? []).filter((event) => !current.some((item) => item.sequence === event.sequence))]);
        }
      } catch (reason) {
        if (active) setError(reason instanceof Error ? reason.message : "Run status unavailable");
      }
    };
    const interval = window.setInterval(() => void poll(), 2000);
    void poll();
    return () => { active = false; window.clearInterval(interval); };
  }, [runId, runStatus, afterSequence]);

  async function startRun() {
    setBusy(true);
    setError("");
    setEvents([]);
    try {
      const response = await fetch("/api/agents/runs", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ selectedSymbols: selected }),
      });
      const payload = await response.json() as AgentRun & { error?: string };
      if (!response.ok) throw new Error(payload.error ?? "Weekly check could not start");
      setRun(payload);
      onRunChange(payload.id);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Weekly check could not start");
    } finally {
      setBusy(false);
    }
  }

  function toggle(symbol: string) {
    setSelected((current) => current.includes(symbol) ? current.filter((item) => item !== symbol) : [...current, symbol]);
  }

  return (
    <div className="view-stack agent-desk">
      <section className="agent-hero">
        <div>
          <p className="eyebrow">TradingAgents integration</p>
          <h2>Weekly portfolio decision room</h2>
          <p>LangGraph routes four analyst roles through bull/bear research, a trader proposal, risk debate, and final portfolio-manager rating. PI then applies its own hard constraints.</p>
        </div>
        <div className={`runtime-state ${runtime?.reachable ? "online" : "offline"}`}>
          <span />
          <div><strong>{runtime?.reachable ? "LangGraph runtime online" : runtime?.configured ? "Runtime unreachable" : "Runtime not configured"}</strong><small>{runtime?.detail ?? "Checking runtime…"}</small></div>
        </div>
      </section>

      {error && <div className="error-banner" role="alert">{error}</div>}

      <section className="agent-grid">
        <article className="panel readiness-card">
          <div className="panel-heading"><div><p className="eyebrow">Preflight</p><h2>Readiness gate</h2></div><span className={`readiness-score ${localChecks.every((check) => check.pass) ? "pass" : "block"}`}>{localChecks.filter((check) => check.pass).length}/{localChecks.length}</span></div>
          <div className="check-list">
            {localChecks.map((check) => <div key={check.label}><span className={check.pass ? "check-pass" : "check-block"}>{check.pass ? "✓" : "!"}</span><strong>{check.label}</strong><small>{check.detail}</small></div>)}
          </div>
          {data.portfolio.isDemo && <p className="agent-note">Fictional demo tickers cannot be sent to live market-data tools. Add or link a real portfolio to run TradingAgents.</p>}
        </article>

        <article className="panel policy-summary">
          <div className="panel-heading"><div><p className="eyebrow">Hard constraints</p><h2>Persistent PI policy</h2></div><span className="audit-chip">Independent</span></div>
          <dl>
            <div><dt>Protected reserve</dt><dd>{inr.format(data.agentPolicy.reserveFloorInr)}</dd></div>
            <div><dt>Deployable cash</dt><dd>{inr.format(data.agentPolicy.deployableCashInr)}</dd></div>
            <div><dt>Position cap</dt><dd>{data.agentPolicy.maxPositionWeightPercent}%</dd></div>
            <div><dt>Single deployment cap</dt><dd>{inr.format(data.agentPolicy.maxSingleDeploymentInr)}</dd></div>
          </dl>
          <p>No equal weighting. No brokerage order can be placed. Agent recommendations never mutate the ledger.</p>
        </article>
      </section>

      <section className="panel universe-card">
        <div className="panel-heading">
          <div><p className="eyebrow">Analysis universe</p><h2>Select holdings for this run</h2></div>
          <div className="selection-actions"><button className="text-button" onClick={() => setSelected(eligibleSymbols.slice(0, 5))}>Top 5</button><button className="text-button" onClick={() => setSelected(eligibleSymbols)}>All mapped</button></div>
        </div>
        <div className="symbol-selector">
          {data.positions.map((position) => (
            <label className={position.mappingStatus === "confirmed" ? "" : "disabled"} key={position.symbol}>
              <input type="checkbox" checked={selected.includes(position.symbol)} disabled={position.mappingStatus !== "confirmed"} onChange={() => toggle(position.symbol)} />
              <span><strong>{position.symbol}</strong><small>{position.analysisSymbol ?? "mapping required"}</small></span>
              <em>{position.allocationPercent.toFixed(1)}%</em>
            </label>
          ))}
        </div>
        <div className="run-controls">
          <p>{selected.length} holding{selected.length === 1 ? "" : "s"} selected. Upstream analysts execute sequentially; larger runs take longer and cost more.</p>
          <button className="primary-button" disabled={!ready || busy || Boolean(run && !terminalStatuses.has(run.status))} onClick={() => void startRun()}>{busy ? "Starting…" : run && !terminalStatuses.has(run.status) ? "Check running…" : "Run weekly check"}</button>
        </div>
      </section>

      {run && <section className="agent-results-grid">
        <article className="panel run-telemetry">
          <div className="panel-heading"><div><p className="eyebrow">Sanitized telemetry</p><h2>Agent activity</h2></div><span className={`run-status ${run.status}`}>{run.status}</span></div>
          <div className="event-stream" aria-live="polite">
            {events.length === 0 && <p>Waiting for runtime events…</p>}
            {events.map((event) => <div key={event.sequence}><time>{new Date(event.occurred_at).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit", second: "2-digit" })}</time><span className={`event-dot ${event.level}`} /><p><strong>{event.symbol ?? event.stage}</strong>{event.message}</p></div>)}
          </div>
        </article>
        <article className="panel run-summary">
          <div className="panel-heading"><div><p className="eyebrow">Decision table</p><h2>Policy-reviewed outcomes</h2></div><span>{run.results.length}/{run.selected_symbols.length}</span></div>
          <div className="result-list">
            {run.results.length === 0 && <p>Results appear here only after a symbol completes.</p>}
            {run.results.map((result) => {
              const blocked = result.policy_checks.some((check) => check.severity === "block");
              return <article key={result.symbol}><div><strong>{result.symbol}</strong><span className={`rating ${result.rating.toLowerCase()}`}>{result.rating}</span></div><p>{result.executive_summary}</p><footer><span>Trader: {result.trader_action}</span><span className={blocked ? "policy-blocked" : "policy-clear"}>{blocked ? "Policy block" : "Policy clear"}</span></footer></article>;
            })}
          </div>
        </article>
      </section>}

      <div className="disclosure-card"><strong>Research, not execution</strong><p>Displayed judgements are model-generated and nondeterministic. Inspect timestamps, sources, policy checks, and the frozen snapshot before relying on any conclusion.</p></div>
    </div>
  );
}
