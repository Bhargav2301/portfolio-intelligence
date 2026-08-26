"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import type {
  ChatResponse,
  DashboardData,
  Evidence,
  HoldingInput,
  HoldingLotInput,
  NormalizedPortfolioImport,
  PortfolioImportSource,
  PortfolioResponse,
  Position,
  SetupData,
} from "../lib/types";
import { AgentDesk } from "./agent-desk";

type View = "overview" | "accounts" | "agents" | "research" | "activity" | "scenario";
type User = { displayName: string; email: string | null };
type ChatMessage = { role: "assistant" | "user"; text: string; evidence?: Evidence[]; citedSymbols?: string[]; restricted?: boolean };

const money = new Intl.NumberFormat("en-IN", {
  style: "currency",
  currency: "INR",
  maximumFractionDigits: 0,
});

const compactMoney = new Intl.NumberFormat("en-IN", {
  style: "currency",
  currency: "INR",
  notation: "compact",
  maximumFractionDigits: 2,
});

const navItems: Array<{ id: View; label: string; glyph: string }> = [
  { id: "overview", label: "Overview", glyph: "O" },
  { id: "accounts", label: "Accounts", glyph: "L" },
  { id: "agents", label: "Agent desk", glyph: "AI" },
  { id: "research", label: "Research", glyph: "R" },
  { id: "activity", label: "Activity", glyph: "A" },
  { id: "scenario", label: "Scenario lab", glyph: "S" },
];

export default function PortfolioApp({ user }: { user: User }) {
  const [data, setData] = useState<PortfolioResponse | null>(null);
  const [view, setView] = useState<View>("overview");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [transactionOpen, setTransactionOpen] = useState(false);
  const [agentRunId, setAgentRunId] = useState<string | null>(null);

  useEffect(() => {
    fetch("/api/portfolio", { cache: "no-store" })
      .then(async (response) => {
        const payload = await response.json();
        if (!response.ok) throw new Error(payload.error ?? "Unable to load portfolio");
        return payload as PortfolioResponse;
      })
      .then(setData)
      .catch((reason: Error) => setError(reason.message))
      .finally(() => setLoading(false));
  }, []);

  const linkedPortfolioOpen = data?.status === "ready" && data.sourceMode === "connected";
  useEffect(() => {
    if (!linkedPortfolioOpen) return;
    let active = true;
    async function backgroundSync() {
      if (document.visibilityState !== "visible") return;
      try {
        const response = await fetch("/api/connections", {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({ action: "sync", provider: "upstox" }),
        });
        if (!response.ok) return;
        const payload = await response.json() as DashboardData;
        if (active) setData(payload);
      } catch {
        // Keep the last successful snapshot; foreground refresh surfaces errors.
      }
    }
    const initial = window.setTimeout(() => void backgroundSync(), 2000);
    const interval = window.setInterval(() => void backgroundSync(), 5 * 60 * 1000);
    return () => { active = false; window.clearTimeout(initial); window.clearInterval(interval); };
  }, [linkedPortfolioOpen]);

  if (loading) return <LoadingState />;
  if (!data) return <ErrorState message={error || "Portfolio data is unavailable"} />;
  if (data.status === "needs_setup") return <Onboarding data={data} user={user} onData={setData} />;

  const dashboard = data;

  async function syncConnectedAccount() {
    setError("");
    try {
      const response = await fetch("/api/connections", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ action: "sync", provider: "upstox" }),
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error ?? "Unable to refresh holdings");
      setData(payload as DashboardData);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to refresh holdings");
    }
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand-lockup">
          <span className="brand-mark" aria-hidden="true"><i /><i /><i /></span>
          <span>Portfolio<br />Intelligence</span>
        </div>
        <nav className="side-nav" aria-label="Primary navigation">
          {navItems.map((item) => (
            <button
              className={view === item.id ? "nav-item active" : "nav-item"}
              key={item.id}
              onClick={() => setView(item.id)}
            >
              <span className="nav-glyph">{item.glyph}</span>
              {item.label}
            </button>
          ))}
        </nav>
        <div className="policy-card">
          <span className="policy-icon">G</span>
          <div>
            <strong>Evidence gate active</strong>
            <p>Personalized advice and trade execution are disabled.</p>
          </div>
        </div>
        <div className="profile-chip">
          <span>{initials(user.displayName)}</span>
          <div><strong>{user.displayName}</strong><small>{user.email ?? "Local demo session"}</small></div>
        </div>
      </aside>

      <main className="workspace">
        <header className="topbar">
          <div>
            <p className="eyebrow">{view === "overview" ? "Portfolio workspace" : navItems.find((item) => item.id === view)?.label}</p>
            <h1>{view === "overview" ? dashboard.portfolio.name : titleForView(view)}</h1>
          </div>
          <div className="topbar-actions">
            <div className={`data-state ${dashboard.sourceMode}`}><span /> {sourceLabel(dashboard)} · {formatDate(dashboard.asOf)}</div>
            {dashboard.sourceMode === "connected" && <button className="quiet-button" onClick={() => void syncConnectedAccount()}>Refresh holdings</button>}
            <button className="primary-button" onClick={() => setTransactionOpen(true)}>Add transaction</button>
          </div>
        </header>

        {error && <div className="error-banner" role="alert">{error}</div>}
        {view === "overview" && <Overview data={dashboard} onViewChange={setView} />}
        {view === "accounts" && <AccountsView data={dashboard} onSync={syncConnectedAccount} />}
        {view === "agents" && <AgentDesk data={dashboard} onRunChange={setAgentRunId} />}
        {view === "research" && <ResearchView data={dashboard} onData={setData} onError={setError} />}
        {view === "activity" && <ActivityView data={dashboard} onData={setData} onError={setError} />}
        {view === "scenario" && <ScenarioView data={dashboard} />}
      </main>

      <ResearchCopilot data={dashboard} agentRunId={agentRunId} />
      {transactionOpen && (
        <TransactionDialog
          data={dashboard}
          onClose={() => setTransactionOpen(false)}
          onData={(next) => { setData(next); setTransactionOpen(false); }}
          onError={setError}
        />
      )}
    </div>
  );
}

function Onboarding({ data, user, onData }: { data: SetupData; user: User; onData: (data: DashboardData) => void }) {
  const [method, setMethod] = useState<"choose" | "manual">("choose");
  const [name, setName] = useState("My Portfolio");
  const [holdings, setHoldings] = useState<HoldingInput[]>([emptyHolding()]);
  const [lots, setLots] = useState<HoldingLotInput[] | undefined>();
  const [source, setSource] = useState<PortfolioImportSource | undefined>();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const upstox = data.connections.find((item) => item.provider === "upstox");

  function updateHolding(index: number, field: keyof HoldingInput, value: string) {
    setHoldings((current) => current.map((holding, row) => row === index
      ? { ...holding, [field]: field === "quantity" || field === "averageCost" || field === "currentPrice" ? Number(value) : value }
      : holding));
  }

  async function save() {
    setBusy(true);
    setError("");
    try {
      const response = await fetch("/api/portfolio", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ mode: "manual", name, baseCurrency: "INR", holdings, lots, source }),
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error ?? "Unable to create portfolio");
      onData(payload as DashboardData);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to create portfolio");
    } finally {
      setBusy(false);
    }
  }

  async function importPortfolioFile(file: File) {
    setError("");
    try {
      if (file.size > 2 * 1024 * 1024) throw new Error("Portfolio import files must be 2 MB or smaller");
      const text = await file.text();
      const isJson = file.name.toLowerCase().endsWith(".json");
      const normalized: {
        holdings: HoldingInput[];
        lots?: HoldingLotInput[];
        portfolioName?: string;
        source?: { filename?: string; sha256?: string };
      } = isJson ? parseNormalizedImport(text) : { holdings: parseCsv(text) };
      const rows = normalized.holdings;
      if (!rows.length) throw new Error("The portfolio file has no holding rows");
      setHoldings(rows);
      setLots(normalized.lots);
      if (normalized.portfolioName) setName(normalized.portfolioName);
      const uploadedHash = await sha256Hex(await file.arrayBuffer());
      const declaredHash = normalized.source?.sha256;
      setSource({
        kind: isJson ? "normalized_json" : "csv",
        filename: normalized.source?.filename ?? file.name,
        sha256: declaredHash && /^[a-f0-9]{64}$/i.test(declaredHash) ? declaredHash : uploadedHash,
      });
      setMethod("manual");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to read portfolio file");
    }
  }

  return (
    <main className="onboarding-shell">
      <header className="onboarding-header">
        <div className="brand-lockup"><span className="brand-mark" aria-hidden="true"><i /><i /><i /></span><span>Portfolio Intelligence</span></div>
        <div className="profile-chip"><span>{initials(user.displayName)}</span><div><strong>{user.displayName}</strong><small>{user.email ?? "Local test session"}</small></div></div>
      </header>
      <section className="onboarding-content">
        <div className="setup-intro">
          <p className="eyebrow">First-run setup</p>
          <h1>Bring your portfolio into one trusted view.</h1>
          <p>Add holdings yourself, import a validated portfolio file, or connect a supported broker through its own sign-in screen. PI does not ask for your broker password.</p>
          <div className="security-strip"><span>Read-only connection</span><span>Encrypted tokens</span><span>No trade execution</span></div>
        </div>

        {error && <div className="error-banner" role="alert">{error}</div>}
        {method === "choose" ? (
          <div className="setup-grid">
            <button className="setup-card recommended" onClick={() => setMethod("manual")}>
              <span className="setup-icon">+</span><span><strong>Add holdings</strong><small>Enter positions and current prices. Best for a quick private test.</small></span><em>Start manually</em>
            </button>
            <label className="setup-card">
              <span className="setup-icon">FILE</span><span><strong>Import portfolio</strong><small>Use canonical CSV or PI normalized JSON. Review every row before saving.</small></span><em>Choose file</em>
              <input type="file" accept=".csv,.json,text/csv,application/json" onChange={(event) => { const file = event.target.files?.[0]; if (file) void importPortfolioFile(file); }} />
            </label>
            <button className="setup-card" disabled={!upstox?.configured} onClick={() => { location.href = "/api/connections/upstox/start"; }}>
              <span className="setup-icon">U</span><span><strong>Link Upstox</strong><small>{upstox?.detail}</small></span><em>{upstox?.configured ? "Connect securely" : "Pilot configuration required"}</em>
            </button>
          </div>
        ) : (
          <form className="manual-setup" onSubmit={(event) => { event.preventDefault(); void save(); }}>
            <div className="manual-heading"><div><button type="button" className="text-button" onClick={() => setMethod("choose")}>← Setup options</button><h2>Portfolio details</h2></div><span>{holdings.length} holding{holdings.length === 1 ? "" : "s"}</span></div>
            <div className="portfolio-fields">
              <label>Portfolio name<input value={name} maxLength={80} onChange={(event) => setName(event.target.value)} required /></label>
              <label>Base currency<select value="INR" disabled><option value="INR">INR · Indian rupee (V1)</option></select></label>
            </div>
            <div className="holding-editor">
              <div className="holding-row holding-labels"><span>Symbol</span><span>Name</span><span>Exchange</span><span>Quantity</span><span>Avg. cost</span><span>Current price</span><span /></div>
              {holdings.map((holding, index) => (
                <div className="holding-row" key={index}>
                  <input aria-label={`Holding ${index + 1} symbol`} value={holding.symbol} onChange={(event) => updateHolding(index, "symbol", event.target.value)} required />
                  <input aria-label={`Holding ${index + 1} name`} value={holding.name} onChange={(event) => updateHolding(index, "name", event.target.value)} required />
                  <input aria-label={`Holding ${index + 1} exchange`} value={holding.exchange} onChange={(event) => updateHolding(index, "exchange", event.target.value)} required />
                  <input aria-label={`Holding ${index + 1} quantity`} type="number" min="0.0001" step="any" value={holding.quantity || ""} onChange={(event) => updateHolding(index, "quantity", event.target.value)} required />
                  <input aria-label={`Holding ${index + 1} average cost`} type="number" min="0" step="any" value={holding.averageCost || ""} onChange={(event) => updateHolding(index, "averageCost", event.target.value)} required />
                  <input aria-label={`Holding ${index + 1} current price`} type="number" min="0" step="any" value={holding.currentPrice || ""} onChange={(event) => updateHolding(index, "currentPrice", event.target.value)} required />
                  <button type="button" aria-label={`Remove holding ${index + 1}`} disabled={holdings.length === 1} onClick={() => setHoldings((current) => current.filter((_, row) => row !== index))}>×</button>
                </div>
              ))}
            </div>
            <div className="manual-actions"><button type="button" className="quiet-button" onClick={() => setHoldings((current) => [...current, emptyHolding()])}>+ Add holding</button><button className="primary-button" disabled={busy} type="submit">{busy ? "Creating tracker…" : "Create portfolio tracker"}</button></div>
            {source && <p className="setup-disclosure">Staged from {source.filename}. The source SHA-256 and normalized rows will be retained; the raw file will not be stored in D1.</p>}
          </form>
        )}
        <p className="setup-disclosure">Legacy XLS files must first pass through the PI normalizer; financial PDFs are evidence sources, not holdings. V1 stores normalized rows and source hashes. Manual prices remain manual until updated; linked account data shows its last successful sync time.</p>
      </section>
    </main>
  );
}

function emptyHolding(): HoldingInput {
  return { symbol: "", name: "", exchange: "NSE", quantity: 0, averageCost: 0, currentPrice: 0 };
}

function parseCsv(input: string): HoldingInput[] {
  const lines: string[][] = [];
  let field = "";
  let row: string[] = [];
  let quoted = false;
  for (let index = 0; index <= input.length; index += 1) {
    const character = input[index] ?? "\n";
    if (character === '"') {
      if (quoted && input[index + 1] === '"') { field += '"'; index += 1; } else quoted = !quoted;
    } else if (character === "," && !quoted) { row.push(field.trim()); field = ""; }
    else if ((character === "\n" || character === "\r") && !quoted) {
      if (character === "\r" && input[index + 1] === "\n") index += 1;
      row.push(field.trim()); field = "";
      if (row.some(Boolean)) lines.push(row);
      row = [];
    } else field += character;
  }
  const header = lines.shift()?.map((value) => value.toLowerCase().replace(/^\ufeff/, "")) ?? [];
  const required = ["symbol", "name", "exchange", "quantity", "average_cost", "current_price"];
  if (!required.every((column) => header.includes(column))) throw new Error(`CSV columns must be: ${required.join(", ")}`);
  if (lines.length > 100) throw new Error("CSV import supports up to 100 holdings");
  return lines.map((values) => ({
    symbol: values[header.indexOf("symbol")] ?? "",
    name: values[header.indexOf("name")] ?? "",
    exchange: values[header.indexOf("exchange")] ?? "",
    quantity: Number(values[header.indexOf("quantity")]),
    averageCost: Number(values[header.indexOf("average_cost")]),
    currentPrice: Number(values[header.indexOf("current_price")]),
  }));
}

function parseNormalizedImport(input: string): {
  holdings: HoldingInput[];
  lots?: HoldingLotInput[];
  portfolioName?: string;
  source?: { filename?: string; sha256?: string };
} {
  let parsed: NormalizedPortfolioImport;
  try {
    parsed = JSON.parse(input) as NormalizedPortfolioImport;
  } catch {
    throw new Error("The normalized import is not valid JSON");
  }
  if (parsed.format !== "pi-portfolio-import/v1" || !Array.isArray(parsed.holdings)) {
    throw new Error("JSON imports must use the pi-portfolio-import/v1 format");
  }
  if (parsed.holdings.length > 100) throw new Error("Portfolio imports support up to 100 holdings");
  return {
    portfolioName: parsed.portfolioName,
    source: parsed.source,
    holdings: parsed.holdings.map((holding) => ({
      symbol: String(holding.symbol ?? ""),
      name: String(holding.name ?? ""),
      exchange: String(holding.exchange ?? ""),
      quantity: Number(holding.quantity),
      averageCost: Number(holding.average_cost),
      currentPrice: Number(holding.current_price),
      analysisSymbol: holding.analysis_symbol ? String(holding.analysis_symbol) : null,
    })),
    lots: parsed.lots?.map((lot) => ({
      symbol: String(lot.symbol ?? ""),
      name: String(lot.name ?? ""),
      exchange: String(lot.exchange ?? ""),
      quantity: Number(lot.quantity),
      unitCost: Number(lot.unit_cost),
      acquiredAt: lot.acquired_at ? String(lot.acquired_at) : null,
      sourceRowNumber: lot.source_row_number === null ? null : Number(lot.source_row_number),
    })),
  };
}

async function sha256Hex(input: ArrayBuffer) {
  const digest = new Uint8Array(await crypto.subtle.digest("SHA-256", input));
  return [...digest].map((byte) => byte.toString(16).padStart(2, "0")).join("");
}

function AccountsView({ data, onSync }: { data: DashboardData; onSync: () => Promise<void> }) {
  return (
    <div className="view-stack">
      <section className="accounts-intro">
        <div><p className="eyebrow">Data connections</p><h2>Accounts & data sources</h2><p>Broker authentication happens on the provider&apos;s site. PI stores only an encrypted access token and reads holdings; it does not place orders.</p></div>
        <div className="security-badge"><strong>Read-only by design</strong><span>OAuth state validation · encrypted at rest</span></div>
      </section>
      <section className="connection-list">
        {data.connections.map((connection) => (
          <article className="connection-card" key={connection.provider}>
            <div className={`provider-mark ${connection.provider}`}>{connection.provider === "upstox" ? "U" : "K"}</div>
            <div className="connection-main"><div><h3>{connection.label}</h3><span className={`connection-status ${connection.status}`}>{connection.status.replaceAll("_", " ")}</span></div><p>{connection.detail}</p>{connection.lastSyncedAt && <small>Last successful sync {formatDateTime(connection.lastSyncedAt)}</small>}</div>
            <div className="connection-actions">
              {connection.status === "connected" ? <button className="primary-button" onClick={() => void onSync()}>Refresh now</button>
                : connection.configured ? <button className="primary-button" onClick={() => { location.href = `/api/connections/${connection.provider}/start`; }}>{connection.status === "expired" ? "Reconnect" : "Connect"}</button>
                  : <button className="quiet-button" disabled>Not enabled</button>}
            </div>
          </article>
        ))}
      </section>
      <section className="sync-explainer"><strong>What “live” means in V1</strong><p>Connected holdings refresh after authorization, shortly after the workspace opens, every five minutes while it remains visible, and whenever you choose Refresh. The tracker shows the last successful sync and keeps the previous snapshot if the broker is unavailable. Manual holdings use the price you entered until you update it.</p></section>
    </div>
  );
}

function Overview({ data, onViewChange }: { data: DashboardData; onViewChange: (view: View) => void }) {
  return (
    <div className="view-stack">
      <section className="metric-grid" aria-label="Portfolio summary">
        <article className="metric-card hero-metric">
          <div className="metric-heading"><span>Total portfolio value</span><span className="demo-pill">{data.sourceMode.toUpperCase()}</span></div>
          <strong>{money.format(data.metrics.totalValue)}</strong>
          <div className="metric-foot positive">
            <span>+{money.format(data.metrics.dayChange)} today</span>
            <span>+{data.metrics.dayChangePercent.toFixed(2)}%</span>
          </div>
        </article>
        <article className="metric-card">
          <div className="metric-heading"><span>Unrealized return</span><span className="mini-dot mint" /></div>
          <strong>{data.metrics.returnPercent >= 0 ? "+" : ""}{data.metrics.returnPercent.toFixed(2)}%</strong>
          <p>{money.format(data.metrics.totalGain)} on {money.format(data.metrics.totalCost)}</p>
        </article>
        <article className="metric-card">
          <div className="metric-heading"><span>Evidence coverage</span><span className="mini-dot blue" /></div>
          <strong>{data.metrics.evidenceCoverage.toFixed(0)}%</strong>
          <p>{data.positions.length} of {data.positions.length} positions source-linked</p>
        </article>
      </section>

      <section className="analysis-grid">
        <article className="panel performance-panel">
          <div className="panel-heading">
            <div><p className="eyebrow">Performance</p><h2>Portfolio value</h2></div>
            <div className="legend"><span className="legend-line" /> Portfolio</div>
          </div>
          <PerformanceChart points={data.valueHistory} />
        </article>
        <article className="panel allocation-panel">
          <div className="panel-heading"><div><p className="eyebrow">Exposure</p><h2>Allocation</h2></div></div>
          <AllocationRing positions={data.positions} />
        </article>
      </section>

      <section className="panel holdings-panel">
        <div className="panel-heading">
          <div><p className="eyebrow">Current positions</p><h2>Holdings</h2></div>
          <button className="text-button" onClick={() => onViewChange("activity")}>View ledger</button>
        </div>
        <HoldingsTable positions={data.positions} />
      </section>
    </div>
  );
}

function PerformanceChart({ points }: { points: DashboardData["valueHistory"] }) {
  const path = useMemo(() => {
    if (points.length < 2) return "";
    const values = points.map((point) => point.value);
    const min = Math.min(...values) * 0.98;
    const max = Math.max(...values) * 1.01;
    return points.map((point, index) => {
      const x = 24 + (index / (points.length - 1)) * 652;
      const y = 176 - ((point.value - min) / (max - min || 1)) * 132;
      return `${index === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
    }).join(" ");
  }, [points]);
  if (points.length < 2) {
    return <div className="snapshot-chart"><strong>{compactMoney.format(points[0]?.value ?? 0)}</strong><span>Current snapshot</span><p>Performance history starts after the first tracked update. PI does not manufacture a backfilled chart.</p></div>;
  }
  const area = `${path} L676,190 L24,190 Z`;

  return (
    <div className="chart-wrap">
      <div className="chart-value">{compactMoney.format(points.at(-1)?.value ?? 0)} <small>current</small></div>
      <svg viewBox="0 0 700 220" role="img" aria-label="Demo portfolio value from May to August">
        <defs>
          <linearGradient id="area-fill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#7ee0ba" stopOpacity=".28" />
            <stop offset="100%" stopColor="#7ee0ba" stopOpacity="0" />
          </linearGradient>
        </defs>
        {[50, 95, 140, 185].map((y) => <line key={y} x1="24" x2="676" y1={y} y2={y} className="grid-line" />)}
        <path d={area} fill="url(#area-fill)" />
        <path d={path} className="portfolio-line" />
        {points.map((point, index) => {
          const x = 24 + (index / (points.length - 1)) * 652;
          return index % 2 === 0 || index === points.length - 1 ? <text key={point.label} x={x} y="214" textAnchor="middle">{point.label}</text> : null;
        })}
      </svg>
    </div>
  );
}

function AllocationRing({ positions }: { positions: Position[] }) {
  const colors = ["#79dfb7", "#6f8cff", "#e7b36f", "#b582e5"];
  const segments = positions.map((position, index) => {
    const length = position.allocationPercent;
    const offset = positions
      .slice(0, index)
      .reduce((sum, item) => sum + item.allocationPercent, 0);
    return <circle key={position.symbol} cx="70" cy="70" r="52" fill="none" stroke={colors[index]} strokeWidth="15" pathLength="100" strokeDasharray={`${length} ${100 - length}`} strokeDashoffset={-offset} />;
  });
  return (
    <div className="allocation-content">
      <div className="ring-wrap">
        <svg viewBox="0 0 140 140" role="img" aria-label="Portfolio allocation by position">
          <circle cx="70" cy="70" r="52" fill="none" stroke="#edf1ef" strokeWidth="15" />
          {segments}
        </svg>
        <div className="ring-label"><strong>{positions.length}</strong><span>positions</span></div>
      </div>
      <div className="allocation-list">
        {positions.map((position, index) => (
          <div key={position.symbol}><span className="color-dot" style={{ background: colors[index] }} /><strong>{position.symbol}</strong><span>{position.allocationPercent.toFixed(1)}%</span></div>
        ))}
      </div>
    </div>
  );
}

function HoldingsTable({ positions }: { positions: Position[] }) {
  return (
    <div className="table-scroll">
      <table>
        <thead><tr><th>Instrument</th><th>Quantity</th><th>Avg. cost</th><th>Market price</th><th>Market value</th><th>Return</th></tr></thead>
        <tbody>
          {positions.map((position) => (
            <tr key={position.symbol}>
              <td><div className="instrument-cell"><span>{position.symbol.slice(0, 2)}</span><div><strong>{position.symbol}</strong><small>{position.name}</small></div></div></td>
              <td>{position.quantity.toLocaleString("en-IN")}</td>
              <td>{money.format(position.averageCost)}</td>
              <td><strong>{money.format(position.currentPrice)}</strong><small className="source-note">{position.priceSource}</small></td>
              <td><strong>{money.format(position.marketValue)}</strong></td>
              <td><span className={position.returnPercent >= 0 ? "return-badge positive" : "return-badge negative"}>{position.returnPercent >= 0 ? "+" : ""}{position.returnPercent.toFixed(2)}%</span></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ResearchView({ data, onData, onError }: {
  data: DashboardData;
  onData: (data: DashboardData) => void;
  onError: (error: string) => void;
}) {
  const [file, setFile] = useState<File | null>(null);
  const [symbol, setSymbol] = useState(data.positions[0]?.symbol ?? "");
  const [title, setTitle] = useState("");
  const [publisher, setPublisher] = useState("");
  const [publishedAt, setPublishedAt] = useState("");
  const [busy, setBusy] = useState(false);

  async function register(event: FormEvent) {
    event.preventDefault();
    if (!file) return;
    setBusy(true);
    onError("");
    try {
      if (file.size > 20 * 1024 * 1024) throw new Error("Evidence PDFs must be 20 MB or smaller");
      const response = await fetch("/api/evidence-documents", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          filename: file.name,
          mimeType: "application/pdf",
          sourceHash: await sha256Hex(await file.arrayBuffer()),
          symbol,
          title,
          publisher,
          publishedAt: publishedAt || null,
        }),
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error ?? "Unable to register evidence");
      onData(payload as DashboardData);
      setFile(null);
      setTitle("");
      setPublisher("");
      setPublishedAt("");
    } catch (reason) {
      onError(reason instanceof Error ? reason.message : "Unable to register evidence");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="view-stack">
      <section className="research-summary">
        <div><p className="eyebrow">Provenance health</p><h2>Every claim needs a source</h2><p>The test release stores source tier, publication time, retrieval time, and a content hash before evidence can support an explanation.</p></div>
        <div className="coverage-score"><strong>{data.metrics.evidenceCoverage.toFixed(0)}</strong><span>% coverage</span></div>
      </section>
      <form className="panel evidence-intake" onSubmit={register}>
        <div className="panel-heading"><div><p className="eyebrow">Manual evidence intake</p><h2>Register a research PDF</h2></div><span className="audit-chip">Metadata only</span></div>
        <p>PI hashes the file in your browser and stores its metadata. The raw PDF is not uploaded to D1; content remains unverified until private document storage and parsing are enabled.</p>
        <div className="evidence-form">
          <label>PDF file<input type="file" accept=".pdf,application/pdf" onChange={(event) => { const selected = event.target.files?.[0] ?? null; setFile(selected); if (selected && !title) setTitle(selected.name.replace(/\.pdf$/i, "")); }} required /></label>
          <label>Holding<select value={symbol} onChange={(event) => setSymbol(event.target.value)} required>{data.positions.map((position) => <option key={position.symbol} value={position.symbol}>{position.symbol}</option>)}</select></label>
          <label>Title<input value={title} maxLength={200} onChange={(event) => setTitle(event.target.value)} required /></label>
          <label>Publisher<input value={publisher} maxLength={120} onChange={(event) => setPublisher(event.target.value)} required /></label>
          <label>Publication date<input type="date" value={publishedAt} onChange={(event) => setPublishedAt(event.target.value)} /></label>
          <button className="primary-button" disabled={!file || busy} type="submit">{busy ? "Registering…" : "Register source"}</button>
        </div>
      </form>
      {data.documents.length > 0 && <section className="panel document-register"><div className="panel-heading"><div><p className="eyebrow">Pending evidence</p><h2>Registered source files</h2></div><span>{data.documents.length} documents</span></div><div className="document-list">{data.documents.map((document) => <article key={document.id}><div><strong>{document.symbol} · {document.title}</strong><span>{document.publisher}{document.publishedAt ? ` · ${formatDate(document.publishedAt)}` : ""}</span></div><div><span className="warning-chip">{document.status.replaceAll("_", " ")}</span><small>SHA-256 {document.sourceHash.slice(0, 12)}…</small></div></article>)}</div></section>}
      <section className="evidence-grid">
        {data.evidence.length === 0 && <article className="empty-evidence"><strong>No verified research evidence yet</strong><p>Registered PDF metadata does not increase evidence coverage. A source must be parsed, reviewed, and verified first.</p></article>}
        {data.evidence.map((item) => (
          <article className="evidence-card" key={item.id}>
            <div className="evidence-meta"><span className="verified-badge">Verified</span><span>Tier {item.sourceTier}</span><span>{formatDate(item.publishedAt)}</span></div>
            <div className="ticker-pill">{item.symbol}</div>
            <h2>{item.title}</h2>
            <p>{item.summary}</p>
            <div className="evidence-footer"><span>{item.publisher}</span><span>Hash checked</span></div>
          </article>
        ))}
      </section>
      <div className="disclosure-card"><strong>Evidence pilot</strong><p>Portfolio values may be current while source documents remain metadata-only. Agent claims cannot cite those files until review changes their status to verified evidence.</p></div>
    </div>
  );
}

function ActivityView({ data, onData, onError }: { data: DashboardData; onData: (data: DashboardData) => void; onError: (error: string) => void }) {
  const [reversing, setReversing] = useState<string | null>(null);
  async function reverse(id: string) {
    setReversing(id);
    onError("");
    try {
      const response = await fetch("/api/transactions", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ action: "reverse", transactionId: id }) });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error ?? "Unable to reverse transaction");
      onData(payload as DashboardData);
    } catch (reason) {
      onError(reason instanceof Error ? reason.message : "Unable to reverse transaction");
    } finally { setReversing(null); }
  }
  return (
    <section className="panel activity-panel">
      <div className="panel-heading"><div><p className="eyebrow">Append-only record</p><h2>Transaction ledger</h2></div><span className="audit-chip">Audit trail intact</span></div>
      <div className="activity-list">
        {data.transactions.map((transaction) => (
          <article key={transaction.id} className={transaction.reversed ? "activity-row reversed" : "activity-row"}>
            <span className={`activity-type ${transaction.type}`}>{transaction.type === "buy" ? "B" : transaction.type === "sell" ? "S" : "R"}</span>
            <div className="activity-main"><strong>{transaction.type === "reversal" ? "Reversal" : transaction.type === "buy" ? "Bought" : "Sold"} {transaction.quantity} {transaction.symbol}</strong><span>{transaction.name} · {formatDate(transaction.occurredAt)}</span></div>
            <div className="activity-amount"><strong>{money.format(transaction.quantity * transaction.unitPrice)}</strong><span>Fees {money.format(transaction.fees)}</span></div>
            {transaction.type !== "reversal" && !transaction.reversed && <button className="quiet-button" disabled={reversing === transaction.id} onClick={() => reverse(transaction.id)}>{reversing === transaction.id ? "Checking…" : "Reverse"}</button>}
            {transaction.reversed && <span className="reversed-label">Reversed</span>}
          </article>
        ))}
      </div>
    </section>
  );
}

function ScenarioView({ data }: { data: DashboardData }) {
  const [symbol, setSymbol] = useState(data.positions[0]?.symbol ?? "");
  const [shock, setShock] = useState(-10);
  const position = data.positions.find((item) => item.symbol === symbol) ?? data.positions[0];
  const impact = position.marketValue * (shock / 100);
  const projectedValue = data.metrics.totalValue + impact;
  return (
    <div className="scenario-grid">
      <section className="panel scenario-controls">
        <p className="eyebrow">Deterministic what-if</p><h2>Price-shock scenario</h2><p>Change one observed price and see the arithmetic portfolio impact. This is not a forecast.</p>
        <label>Instrument<select value={symbol} onChange={(event) => setSymbol(event.target.value)}>{data.positions.map((item) => <option value={item.symbol} key={item.symbol}>{item.symbol} · {item.name}</option>)}</select></label>
        <label>Price shock <strong className={shock >= 0 ? "positive" : "negative"}>{shock > 0 ? "+" : ""}{shock}%</strong><input type="range" min="-40" max="40" step="1" value={shock} onChange={(event) => setShock(Number(event.target.value))} /></label>
        <div className="range-labels"><span>-40%</span><span>0</span><span>+40%</span></div>
      </section>
      <section className="panel scenario-output">
        <div className="scenario-status">Scenario result</div>
        <p>Estimated portfolio value</p><strong>{money.format(projectedValue)}</strong>
        <div className={impact >= 0 ? "impact-card positive" : "impact-card negative"}><span>Portfolio impact</span><strong>{impact >= 0 ? "+" : ""}{money.format(impact)}</strong><small>{((impact / data.metrics.totalValue) * 100).toFixed(2)}% of current portfolio</small></div>
        <div className="scenario-equation"><span>{position.symbol} market value</span><strong>{money.format(position.marketValue)}</strong><span>Shocked value</span><strong>{money.format(position.marketValue + impact)}</strong></div>
      </section>
    </div>
  );
}

function ResearchCopilot({ data, agentRunId }: { data: DashboardData; agentRunId: string | null }) {
  const [prompt, setPrompt] = useState("");
  const [busy, setBusy] = useState(false);
  const [mode, setMode] = useState<"portfolio" | "agent">("portfolio");
  const [messages, setMessages] = useState<ChatMessage[]>([
    { role: "assistant", text: `I can explain ${data.portfolio.name} using deterministic analytics and the evidence currently attached. Try asking about performance, concentration risk, sources, or scenarios.` },
  ]);
  async function ask(value: string) {
    const clean = value.trim();
    if (!clean || busy) return;
    setMessages((current) => [...current, { role: "user", text: clean }]);
    setPrompt("");
    setBusy(true);
    try {
      const response = await fetch(mode === "agent" ? "/api/agents/chat" : "/api/chat", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(mode === "agent" ? { prompt: clean, runId: agentRunId } : { prompt: clean }),
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error ?? "Unable to answer");
      const answer = payload as ChatResponse & { cited_symbols?: string[] };
      setMessages((current) => [...current, { role: "assistant", text: answer.answer, evidence: answer.evidence, citedSymbols: answer.cited_symbols, restricted: answer.status === "restricted" }]);
    } catch (reason) {
      setMessages((current) => [...current, { role: "assistant", text: reason instanceof Error ? reason.message : "Unable to answer" }]);
    } finally { setBusy(false); }
  }
  function submit(event: FormEvent) { event.preventDefault(); void ask(prompt); }
  return (
    <aside className="copilot">
      <div className="copilot-heading"><div><span className="copilot-mark">PI</span><div><strong>Research copilot</strong><small><i /> Evidence-gated</small></div></div><button aria-label="Copilot information">i</button></div>
      <div className="copilot-modes"><button className={mode === "portfolio" ? "active" : ""} onClick={() => setMode("portfolio")}>Portfolio</button><button className={mode === "agent" ? "active" : ""} onClick={() => setMode("agent")}>Agent run</button></div>
      <div className="chat-stream">
        {messages.map((message, index) => (
          <div className={`chat-message ${message.role}`} key={`${message.role}-${index}`}>
            {message.role === "assistant" && <span className="chat-avatar">PI</span>}
            <div><p>{message.text}</p>{message.restricted && <span className="restricted-chip">Policy restriction applied</span>}{message.evidence && message.evidence.length > 0 && <div className="chat-sources">{message.evidence.slice(0, 2).map((item) => <span key={item.id}>{item.symbol} · {item.title}</span>)}</div>}{message.citedSymbols && message.citedSymbols.length > 0 && <div className="chat-sources">{message.citedSymbols.map((symbol) => <span key={symbol}>{symbol} · completed agent artifact</span>)}</div>}</div>
          </div>
        ))}
        {busy && <div className="chat-message assistant"><span className="chat-avatar">PI</span><div className="thinking"><i /><i /><i /></div></div>}
      </div>
      <div className="suggestion-list">
        {(mode === "agent" ? ["Summarize the latest run", "Why this rating?", "Which policy checks applied?"] : ["What drives my returns?", "Show concentration risk", "What sources are attached?"]).map((suggestion) => <button key={suggestion} onClick={() => void ask(suggestion)}>{suggestion}</button>)}
      </div>
      <form className="chat-input" onSubmit={submit}><input value={prompt} onChange={(event) => setPrompt(event.target.value)} placeholder={mode === "agent" ? "Ask about a completed run…" : "Ask about this portfolio…"} aria-label="Ask the research copilot" /><button disabled={!prompt.trim() || busy || (mode === "agent" && !agentRunId)} aria-label="Send question">↑</button></form>
      <p className="copilot-disclaimer">{mode === "agent" && !agentRunId ? "Start an Agent desk run to enable run Q&A." : `Research intelligence · ${data.sourceMode} holdings · not investment advice.`}</p>
    </aside>
  );
}

function TransactionDialog({ data, onClose, onData, onError }: { data: DashboardData; onClose: () => void; onData: (data: DashboardData) => void; onError: (error: string) => void }) {
  const [type, setType] = useState<"buy" | "sell">("buy");
  const [symbol, setSymbol] = useState(data.positions[0]?.symbol ?? "NOVA");
  const selected = data.positions.find((position) => position.symbol === symbol) ?? data.positions[0];
  const [quantity, setQuantity] = useState("1");
  const [price, setPrice] = useState(String(selected?.currentPrice ?? 0));
  const [fees, setFees] = useState("0");
  const [date, setDate] = useState("2026-08-13");
  const [reviewing, setReviewing] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  function selectSymbol(next: string) { setSymbol(next); const nextPosition = data.positions.find((position) => position.symbol === next); if (nextPosition) setPrice(String(nextPosition.currentPrice)); }
  async function submit() {
    setSubmitting(true); onError("");
    try {
      const idempotencyKey = `ui-${Date.now()}-${Math.random().toString(36).slice(2)}`;
      const response = await fetch("/api/transactions", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ symbol, type, quantity: Number(quantity), unitPrice: Number(price), fees: Number(fees), occurredAt: `${date}T05:00:00.000Z`, idempotencyKey }) });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error ?? "Unable to record transaction");
      onData(payload as DashboardData);
    } catch (reason) { onError(reason instanceof Error ? reason.message : "Unable to record transaction"); setReviewing(false); }
    finally { setSubmitting(false); }
  }
  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
      <section className="transaction-dialog" role="dialog" aria-modal="true" aria-labelledby="transaction-title">
        <div className="dialog-heading"><div><p className="eyebrow">Append to ledger</p><h2 id="transaction-title">{reviewing ? "Confirm transaction" : "Add transaction"}</h2></div><button onClick={onClose} aria-label="Close transaction dialog">×</button></div>
        {!reviewing ? <form onSubmit={(event) => { event.preventDefault(); setReviewing(true); }}>
          <div className="segmented"><button type="button" className={type === "buy" ? "active" : ""} onClick={() => setType("buy")}>Buy</button><button type="button" className={type === "sell" ? "active" : ""} onClick={() => setType("sell")}>Sell</button></div>
          <div className="form-grid"><label>Instrument<select value={symbol} onChange={(event) => selectSymbol(event.target.value)}>{data.positions.map((position) => <option key={position.symbol} value={position.symbol}>{position.symbol} · {position.name}</option>)}</select></label><label>Trade date<input type="date" value={date} onChange={(event) => setDate(event.target.value)} required /></label><label>Quantity<input type="number" min="0.0001" step="0.0001" value={quantity} onChange={(event) => setQuantity(event.target.value)} required /></label><label>Unit price (INR)<input type="number" min="0" step="0.01" value={price} onChange={(event) => setPrice(event.target.value)} required /></label><label>Fees (INR)<input type="number" min="0" step="0.01" value={fees} onChange={(event) => setFees(event.target.value)} required /></label></div>
          <div className="validation-note"><strong>Validation before write</strong><span>The system checks instrument identity, non-negative values, available quantity, and duplicate risk.</span></div>
          <button className="primary-button full" type="submit">Review transaction</button>
        </form> : <div className="confirmation-view">
          <div className="confirmation-icon">✓</div><p>You are about to record an immutable ledger event.</p>
          <dl><div><dt>Action</dt><dd>{type.toUpperCase()} {quantity} {symbol}</dd></div><div><dt>Unit price</dt><dd>{money.format(Number(price))}</dd></div><div><dt>Fees</dt><dd>{money.format(Number(fees))}</dd></div><div><dt>Total</dt><dd>{money.format(Number(quantity) * Number(price) + Number(fees))}</dd></div></dl>
          <div className="dialog-actions"><button className="quiet-button" onClick={() => setReviewing(false)}>Go back</button><button className="primary-button" disabled={submitting} onClick={() => void submit()}>{submitting ? "Recording…" : "Confirm and record"}</button></div>
        </div>}
      </section>
    </div>
  );
}

function LoadingState() { return <main className="loading-screen"><span className="brand-mark"><i /><i /><i /></span><h1>Portfolio Intelligence</h1><div className="loading-bar"><i /></div><p>Preparing deterministic analytics…</p></main>; }
function ErrorState({ message }: { message: string }) { return <main className="loading-screen"><span className="error-symbol">!</span><h1>Portfolio unavailable</h1><p>{message}</p><button className="primary-button" onClick={() => location.reload()}>Try again</button></main>; }
function initials(value: string) { return value.split(/\s+/).slice(0, 2).map((part) => part[0]?.toUpperCase()).join("") || "PI"; }
function formatDate(value: string) { return new Intl.DateTimeFormat("en-IN", { day: "2-digit", month: "short", year: "numeric" }).format(new Date(value)); }
function formatDateTime(value: string) { return new Intl.DateTimeFormat("en-IN", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" }).format(new Date(value)); }
function sourceLabel(data: DashboardData) { return data.sourceMode === "connected" ? "Linked holdings" : data.sourceMode === "manual" ? "Manual prices" : "Demo data"; }
function titleForView(view: View) { return view === "accounts" ? "Accounts & connections" : view === "agents" ? "Agent decision room" : view === "research" ? "Evidence & research" : view === "activity" ? "Transaction history" : "Scenario lab"; }
