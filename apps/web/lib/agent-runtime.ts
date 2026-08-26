import { getDashboard } from "./data";
import type { AgentRun, AgentRunEvent, AgentRuntimeStatus, DashboardData } from "./types";

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
      configured: false,
      reachable: false,
      runtime: "tradingagents",
      version: null,
      detail: "TradingAgents runtime credentials are not configured for this deployment.",
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
      version: health.version ?? null,
      detail: "TradingAgents research runtime is reachable. Trade execution remains disabled.",
    };
  } catch {
    return {
      configured: true,
      reachable: false,
      runtime: "tradingagents",
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

export async function startAgentRun(ownerEmail: string, selectedSymbols?: string[]) {
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
  const response = await runtimeFetch(`/v1/runs/${encodeURIComponent(runId)}`, ownerEmail);
  return response.json() as Promise<AgentRun>;
}

export async function getAgentEvents(ownerEmail: string, runId: string, after = 0) {
  const response = await runtimeFetch(`/v1/runs/${encodeURIComponent(runId)}/events?after=${Math.max(0, after)}`, ownerEmail);
  return response.json() as Promise<{ events: AgentRunEvent[]; next: number }>;
}

export async function askAgentRun(ownerEmail: string, prompt: string, runId?: string) {
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
