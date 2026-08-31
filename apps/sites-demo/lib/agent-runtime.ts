import { getDashboard } from "./data";
import type { AgentPolicyCheck, AgentRun, AgentRunEvent, AgentRuntimeStatus, AgentSymbolResult, DashboardData } from "./types";

function runtimeConfig() {
  const environment = globalThis.__PI_ENV ?? {};
  const url = environment.TRADING_AGENTS_API_URL?.replace(/\/$/, "");
  const token = environment.TRADING_AGENTS_API_TOKEN;
  return url && token ? { url, token } : null;
}

async function runtimeFetch(path: string, ownerEmail: string, init: RequestInit = {}) {
  const config = runtimeConfig();
  if (!config) throw new Error("AGENT_RUNTIME_NOT_CONFIGURED");
  const response = await fetch(`${config.url}${path}`, {
    ...init,
    headers: {
      authorization: `Bearer ${config.token}`,
      "x-pi-owner-email": ownerEmail,
      ...(init.body ? { "content-type": "application/json" } : {}),
      ...init.headers,
    },
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({})) as { detail?: string; error?: string };
    throw new Error(payload.detail || payload.error || `Agent runtime returned ${response.status}`);
  }
  return response;
}

export async function getAgentRuntimeStatus(): Promise<AgentRuntimeStatus> {
  const config = runtimeConfig();
  if (!config) {
    return {
      configured: true,
      reachable: true,
      runtime: "tradingagents",
      mode: "demo_safe",
      version: "sites-demo-adapter/1.0",
      detail: "Deterministic demo adapter online. The external Python LangGraph runtime is not connected.",
    };
  }
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 3000);
  try {
    const response = await fetch(`${config.url}/health`, { signal: controller.signal });
    if (!response.ok) throw new Error("Health check failed");
    const health = await response.json() as { version?: string };
    return {
      configured: true,
      reachable: true,
      runtime: "tradingagents",
      mode: "external",
      version: health.version ?? null,
      detail: "TradingAgents research runtime is reachable. Trade execution remains disabled.",
    };
  } catch {
    return {
      configured: true,
      reachable: false,
      runtime: "tradingagents",
      mode: "external",
      version: null,
      detail: "Runtime is configured but did not pass its health check.",
    };
  } finally {
    clearTimeout(timeout);
  }
}

function bytesToHex(bytes: Uint8Array) {
  return [...bytes].map((byte) => byte.toString(16).padStart(2, "0")).join("");
}

async function snapshotIdentity(dashboard: DashboardData) {
  const canonical = JSON.stringify({
    portfolio: dashboard.portfolio.id,
    asOf: dashboard.asOf,
    positions: dashboard.positions.map((position) => ({
      symbol: position.symbol,
      exchange: position.exchange,
      analysisSymbol: position.analysisSymbol,
      quantity: position.quantity,
      averageCost: position.averageCost,
      currentPrice: position.currentPrice,
    })).sort((left, right) => left.symbol.localeCompare(right.symbol)),
  });
  const digest = new Uint8Array(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(canonical)));
  return { id: `${dashboard.portfolio.id}:${dashboard.asOf}`, hash: bytesToHex(digest) };
}

function selectedPositions(dashboard: DashboardData, selectedSymbols?: string[]) {
  const requested = new Set((selectedSymbols ?? []).map((symbol) => symbol.trim().toUpperCase()).filter(Boolean));
  return dashboard.positions.filter((position) => requested.size === 0 || requested.has(position.symbol));
}

function demoPolicyChecks(dashboard: DashboardData): AgentPolicyCheck[] {
  return [
    {
      code: "NO_EXECUTION",
      severity: "pass",
      message: "This adapter cannot place or stage brokerage orders.",
    },
    {
      code: "RESERVE_FLOOR",
      severity: "pass",
      message: `The protected reserve remains ₹${dashboard.agentPolicy.reserveFloorInr.toLocaleString("en-IN")}; this research run does not deploy cash.`,
    },
    {
      code: "HUMAN_CONFIRMATION",
      severity: "pass",
      message: "Any future portfolio action requires separate human confirmation.",
    },
  ];
}

function demoResult(dashboard: DashboardData, symbol: string): AgentSymbolResult {
  const position = dashboard.positions.find((item) => item.symbol === symbol);
  if (!position) throw new Error(`Unknown portfolio symbol: ${symbol}`);
  const evidence = dashboard.evidence.filter((item) => item.symbol === symbol && item.status === "verified");
  const rating: AgentSymbolResult["rating"] = evidence.length === 0
    ? "ABSTAIN"
    : position.returnPercent >= 5
      ? "BULLISH"
      : position.returnPercent <= -5
        ? "BEARISH"
        : "NEUTRAL";
  const concentration = position.allocationPercent > dashboard.agentPolicy.maxPositionWeightPercent;
  const checks: AgentPolicyCheck[] = [
    {
      code: "EVIDENCE_GATE",
      severity: evidence.length ? "pass" : "warning",
      message: evidence.length
        ? `${evidence.length} verified evidence record${evidence.length === 1 ? "" : "s"} support traceable context.`
        : "No verified evidence is attached; the adapter abstains.",
      symbol,
    },
    {
      code: "POSITION_CAP",
      severity: concentration ? "block" : "pass",
      message: concentration
        ? `${position.allocationPercent.toFixed(1)}% allocation exceeds the ${dashboard.agentPolicy.maxPositionWeightPercent}% policy cap.`
        : `${position.allocationPercent.toFixed(1)}% allocation is within the ${dashboard.agentPolicy.maxPositionWeightPercent}% policy cap.`,
      symbol,
    },
  ];
  const evidencePhrase = evidence.length
    ? `${evidence.length} verified record${evidence.length === 1 ? "" : "s"}`
    : "no verified records";
  const summary = rating === "ABSTAIN"
    ? `${symbol} is classified ABSTAIN because the snapshot has ${evidencePhrase}. No directional inference is produced.`
    : `${symbol} is classified ${rating} from its ${position.returnPercent.toFixed(1)}% snapshot return, reviewed against ${evidencePhrase}. This is a research signal, not a trade instruction.`;
  return {
    symbol,
    analysis_symbol: position.analysisSymbol ?? `${position.exchange}:${position.symbol}`,
    rating,
    executive_summary: summary,
    investment_thesis: `Snapshot performance is ${position.returnPercent.toFixed(1)}%, allocation is ${position.allocationPercent.toFixed(1)}%, and evidence coverage is ${evidence.length ? "verified" : "insufficient"}.`,
    trader_action: "No action",
    trader_reasoning: "The Sites adapter stops at a research classification and never proposes or executes an order.",
    research_judgement: evidence.length
      ? `The analyst roles agree that the supplied snapshot and cited evidence are sufficient for a ${rating} scenario label.`
      : "The analyst roles do not have enough verified evidence for a directional label.",
    risk_judgement: concentration
      ? "The portfolio policy blocks reliance on this signal because the position exceeds its concentration cap."
      : "No concentration block is triggered, but market, liquidity, and source-recency risk remain.",
    policy_checks: checks,
    reports: {
      market: `Snapshot return: ${position.returnPercent.toFixed(1)}%; price as of ${position.priceAsOf}.`,
      fundamentals: evidence.length ? evidence.map((item) => item.title).join(" | ") : "No verified fundamental evidence supplied.",
      news: evidence.length ? evidence.map((item) => `${item.publisher}: ${item.summary}`).join(" | ") : "No verified news evidence supplied.",
      social: "Social-signal inference is disabled in the deterministic demo adapter.",
      debate: `Bull/bear review resolved to ${rating}; the risk layer ${concentration ? "raised a concentration block" : "raised no concentration block"}.`,
    },
  };
}

function demoEvents(results: AgentSymbolResult[], occurredAt: string): AgentRunEvent[] {
  return [
    { sequence: 1, occurred_at: occurredAt, level: "info", stage: "snapshot", message: "Frozen portfolio snapshot loaded; no live market call was made." },
    { sequence: 2, occurred_at: occurredAt, level: "info", stage: "analysts", message: "Market, fundamentals, news, and social-role inputs were normalized." },
    { sequence: 3, occurred_at: occurredAt, level: "info", stage: "debate", message: "Bull and bear cases were reconciled into scenario labels." },
    { sequence: 4, occurred_at: occurredAt, level: "info", stage: "risk", message: "Concentration, reserve, and human-confirmation policies were applied." },
    ...results.map((result, index): AgentRunEvent => ({
      sequence: index + 5,
      occurred_at: occurredAt,
      level: result.rating === "ABSTAIN" || result.policy_checks.some((check) => check.severity === "block") ? "warning" : "info",
      stage: "signal",
      symbol: result.symbol,
      message: `${result.rating}; no action generated.`,
    })),
  ];
}

async function startDemoRun(ownerEmail: string, selectedSymbols?: string[]): Promise<AgentRun> {
  const dashboard = await getDashboard(ownerEmail);
  const positions = selectedPositions(dashboard, selectedSymbols);
  if (positions.length === 0) throw new Error("Select at least one portfolio holding");
  const identity = await snapshotIdentity(dashboard);
  const createdAt = new Date().toISOString();
  const results = positions.map((position) => demoResult(dashboard, position.symbol));
  const events = demoEvents(results, createdAt);
  return {
    id: `demo-${identity.hash.slice(0, 12)}-${Date.now().toString(36)}`,
    portfolio_id: dashboard.portfolio.id,
    snapshot_id: identity.id,
    mode: "weekly_trigger",
    status: "completed",
    created_at: createdAt,
    started_at: createdAt,
    completed_at: createdAt,
    selected_symbols: positions.map((position) => position.symbol),
    policy_checks: demoPolicyChecks(dashboard),
    results,
    error: null,
    last_event_sequence: events.length,
    workflow_engine: "tradingagents-adapter",
    workflow_version: "sites-demo-adapter/1.0",
    events,
  };
}

export async function startAgentRun(ownerEmail: string, selectedSymbols?: string[]) {
  if (!runtimeConfig()) return startDemoRun(ownerEmail, selectedSymbols);
  const dashboard = await getDashboard(ownerEmail);
  const identity = await snapshotIdentity(dashboard);
  const body = {
    portfolio_id: dashboard.portfolio.id,
    snapshot_id: identity.id,
    snapshot_hash: identity.hash,
    as_of: dashboard.asOf,
    analysis_date: dashboard.asOf.slice(0, 10),
    mode: "weekly_trigger",
    holdings: dashboard.positions.map((position) => ({
      symbol: position.symbol,
      name: position.name,
      exchange: position.exchange,
      analysis_symbol: position.analysisSymbol,
      quantity: position.quantity,
      average_cost: position.averageCost,
      current_price: position.currentPrice,
      market_value: position.marketValue,
      allocation_percent: position.allocationPercent,
      price_as_of: position.priceAsOf,
    })),
    selected_symbols: selectedSymbols ?? [],
    selected_analysts: ["market", "social", "news", "fundamentals"],
    policy: {
      reserve_floor_inr: dashboard.agentPolicy.reserveFloorInr,
      deployable_cash_inr: dashboard.agentPolicy.deployableCashInr,
      max_position_weight_percent: dashboard.agentPolicy.maxPositionWeightPercent,
      max_single_deployment_inr: dashboard.agentPolicy.maxSingleDeploymentInr,
      data_max_age_minutes: dashboard.agentPolicy.dataMaxAgeMinutes,
      no_equal_weighting: dashboard.agentPolicy.noEqualWeighting,
      require_human_confirmation: dashboard.agentPolicy.requireHumanConfirmation,
    },
    dry_run: false,
  };
  const response = await runtimeFetch("/v1/runs", ownerEmail, { method: "POST", body: JSON.stringify(body) });
  return response.json() as Promise<AgentRun>;
}

export async function getAgentRun(ownerEmail: string, runId: string) {
  if (!runtimeConfig()) throw new Error("Demo runs complete synchronously and are returned in the start response");
  const response = await runtimeFetch(`/v1/runs/${encodeURIComponent(runId)}`, ownerEmail);
  return response.json() as Promise<AgentRun>;
}

export async function getAgentEvents(ownerEmail: string, runId: string, after = 0) {
  if (!runtimeConfig()) throw new Error("Demo events are returned with the completed run");
  const response = await runtimeFetch(`/v1/runs/${encodeURIComponent(runId)}/events?after=${Math.max(0, after)}`, ownerEmail);
  return response.json() as Promise<{ events: AgentRunEvent[]; next: number }>;
}

export async function askAgentRun(ownerEmail: string, prompt: string, runId?: string) {
  if (!runtimeConfig()) {
    const dashboard = await getDashboard(ownerEmail);
    const restricted = /\b(buy|sell|order|execute|trade|quantity|target price|stop loss)\b/i.test(prompt);
    const mentioned = dashboard.positions.filter((position) => prompt.toUpperCase().includes(position.symbol.toUpperCase()));
    const positions = mentioned.length ? mentioned : dashboard.positions.slice(0, 3);
    const results = positions.map((position) => demoResult(dashboard, position.symbol));
    const answer = restricted
      ? "The demo adapter cannot provide or execute a buy, sell, quantity, target-price, or stop-loss instruction. It can explain evidence, snapshot performance, concentration, and the BULLISH/BEARISH/NEUTRAL/ABSTAIN research labels."
      : results.map((result) => `${result.symbol}: ${result.executive_summary}`).join(" ");
    return {
      answer,
      run_id: runId || `demo-chat-${Date.now().toString(36)}`,
      as_of: dashboard.asOf,
      status: restricted ? "restricted" as const : "grounded" as const,
      cited_symbols: results.map((result) => result.symbol),
    };
  }
  const response = await runtimeFetch("/v1/chat", ownerEmail, {
    method: "POST",
    body: JSON.stringify({ prompt, run_id: runId || null }),
  });
  return response.json() as Promise<{
    answer: string;
    run_id: string;
    as_of: string;
    status: "grounded" | "restricted";
    cited_symbols: string[];
  }>;
}
