"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";

import {
  AgentResult,
  Portfolio,
  UploadResult,
  requestJson,
} from "@/lib/api";


const portfolioTypeLabel: Record<Portfolio["portfolio_type"], string> = {
  self_managed: "Self-managed",
  pms: "PMS",
  model: "Model",
  interest: "Portfolio of Interest",
};


function formatInr(value: string | null | undefined) {
  if (!value) return "—";
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  }).format(Number(value));
}


export default function PortfolioWorkspace() {
  const [portfolios, setPortfolios] = useState<Portfolio[]>([]);
  const [selectedId, setSelectedId] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [notice, setNotice] = useState<string>("");
  const [error, setError] = useState<string>("");
  const [upload, setUpload] = useState<UploadResult | null>(null);
  const [agent, setAgent] = useState<AgentResult | null>(null);
  const [chatQuestion, setChatQuestion] = useState(
    "What should I review before making any investment decision?",
  );
  const [agentRunning, setAgentRunning] = useState(false);

  const selected = useMemo(
    () => portfolios.find((portfolio) => portfolio.id === selectedId) ?? portfolios[0],
    [portfolios, selectedId],
  );

  const loadPortfolios = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const data = await requestJson<Portfolio[]>("/api/core/v1/portfolios");
      setPortfolios(data);
      setSelectedId((current) => current || data[0]?.id || "");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not load portfolios.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadPortfolios();
  }, [loadPortfolios]);

  async function createPortfolio(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setNotice("");
    const form = new FormData(event.currentTarget);
    try {
      const created = await requestJson<Portfolio>("/api/core/v1/portfolios", {
        method: "POST",
        body: JSON.stringify({
          name: form.get("name"),
          portfolio_type: form.get("portfolio_type"),
          base_currency: "INR",
          benchmark_code: form.get("benchmark_code"),
          valuation_timezone: "Asia/Kolkata",
        }),
      });
      setPortfolios((current) => [created, ...current]);
      setSelectedId(created.id);
      setNotice("Portfolio created. The next step is to add a trusted data source.");
      event.currentTarget.reset();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Portfolio could not be created.");
    }
  }

  async function uploadFile(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selected) return;
    setError("");
    setNotice("Checking file structure and safety…");
    setUpload(null);
    const form = new FormData(event.currentTarget);
    form.set("portfolio_id", selected.id);
    try {
      const result = await requestJson<UploadResult>("/api/core/v1/uploads", {
        method: "POST",
        body: form,
      });
      setUpload(result);
      setNotice("File accepted into quarantine. Review is required before publication.");
    } catch (caught) {
      setNotice("");
      setError(caught instanceof Error ? caught.message : "File could not be accepted.");
    }
  }

  async function askAgent(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selected || !chatQuestion.trim()) return;
    setAgentRunning(true);
    setAgent(null);
    setError("");
    try {
      const result = await requestJson<AgentResult>("/api/agents/v1/agent-runs", {
        method: "POST",
        body: JSON.stringify({
          portfolio_id: selected.id,
          question: chatQuestion,
        }),
      });
      setAgent(result);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The agent run failed.");
    } finally {
      setAgentRunning(false);
    }
  }

  return (
    <main className="shell">
      <a className="skip-link" href="#workspace">
        Skip to portfolio workspace
      </a>

      <header className="topbar">
        <div className="brand">
          <span className="brand-mark" aria-hidden="true">PI</span>
          <div>
            <strong>Portfolio Intelligence</strong>
            <span>Read-only decision workspace</span>
          </div>
        </div>
        <div className="top-actions">
          <span className="mode-pill">Analytics mode</span>
          <button className="avatar" aria-label="Open account settings">B</button>
        </div>
      </header>

      <div className="app-grid">
        <aside className="sidebar" aria-label="Primary navigation">
          <nav>
            <a className="nav-item active" href="#overview">
              <span aria-hidden="true">01</span> Overview
            </a>
            <a className="nav-item" href="#data">
              <span aria-hidden="true">02</span> Data sources
            </a>
            <a className="nav-item" href="#ask">
              <span aria-hidden="true">03</span> Ask AI
            </a>
            <a className="nav-item" href="#rules">
              <span aria-hidden="true">04</span> Rules
            </a>
          </nav>
          <div className="sidebar-note">
            <span className="eyebrow">Product boundary</span>
            <p>No order can be placed from this application.</p>
          </div>
        </aside>

        <section className="workspace" id="workspace" aria-busy={loading}>
          <div className="workspace-head">
            <div>
              <span className="eyebrow">Portfolio workspace</span>
              <h1>{selected?.name ?? "Create your first portfolio"}</h1>
              <p>
                {selected
                  ? portfolioTypeLabel[selected.portfolio_type] + " · " + selected.benchmark_code
                  : "Start with what you own or build a roadmap from scratch."}
              </p>
            </div>
            {portfolios.length > 0 && (
              <label className="select-label">
                <span>Portfolio</span>
                <select
                  value={selected?.id ?? ""}
                  onChange={(event) => {
                    setSelectedId(event.target.value);
                    setUpload(null);
                    setAgent(null);
                  }}
                >
                  {portfolios.map((portfolio) => (
                    <option key={portfolio.id} value={portfolio.id}>
                      {portfolio.name}
                    </option>
                  ))}
                </select>
              </label>
            )}
          </div>

          {error && <div className="alert error" role="alert"><strong>Action needed.</strong> {error}</div>}
          {notice && <div className="alert info" role="status">{notice}</div>}

          {!selected ? (
            <section className="onboarding" aria-labelledby="onboarding-title">
              <div className="section-heading">
                <span className="eyebrow">Step 1 of 3</span>
                <h2 id="onboarding-title">How do you want to begin?</h2>
                <p>Create a clean workspace. No sample holdings or demo returns will be added.</p>
              </div>
              <div className="path-grid">
                <article className="path-card featured">
                  <span className="card-index">01</span>
                  <h3>Analyze what I own</h3>
                  <p>For brokerage files, statements, PMS portfolios, and manual records.</p>
                </article>
                <article className="path-card">
                  <span className="card-index">02</span>
                  <h3>Build a starting roadmap</h3>
                  <p>For a goal, horizon, contribution plan, reserve, and risk profile.</p>
                </article>
              </div>
              <form className="create-form" onSubmit={createPortfolio}>
                <label>
                  <span>Portfolio name</span>
                  <input name="name" required minLength={2} placeholder="Example: Core Equity" />
                </label>
                <label>
                  <span>Portfolio type</span>
                  <select name="portfolio_type" defaultValue="self_managed">
                    <option value="self_managed">Self-managed</option>
                    <option value="pms">PMS</option>
                    <option value="model">Model portfolio</option>
                    <option value="interest">Portfolio of Interest</option>
                  </select>
                </label>
                <label>
                  <span>Benchmark</span>
                  <input name="benchmark_code" required defaultValue="NIFTY_500_TRI" />
                </label>
                <button className="primary-button" type="submit">Create clean portfolio</button>
              </form>
            </section>
          ) : (
            <>
              <section className="quality-banner" aria-label="Portfolio data status">
                <div className="quality-icon" aria-hidden="true">!</div>
                <div>
                  <strong>Portfolio data is partial</strong>
                  <p>No approved ledger has been published. AI analysis is limited until reconciliation.</p>
                </div>
                <a href="#data">Add or review data</a>
              </section>

              <section id="overview" aria-labelledby="overview-title">
                <div className="section-heading horizontal">
                  <div>
                    <span className="eyebrow">As of now · No market data loaded</span>
                    <h2 id="overview-title">Portfolio overview</h2>
                  </div>
                  <span className="status-text"><i aria-hidden="true" /> Needs review</span>
                </div>

                <div className="metric-grid">
                  <article className="metric-card">
                    <span>Current value</span>
                    <strong>—</strong>
                    <small>Waiting for approved holdings</small>
                  </article>
                  <article className="metric-card">
                    <span>Net invested</span>
                    <strong>—</strong>
                    <small>Waiting for transaction history</small>
                  </article>
                  <article className="metric-card">
                    <span>Return vs benchmark</span>
                    <strong>—</strong>
                    <small>No return claim without cash flows</small>
                  </article>
                  <article className="metric-card protected">
                    <span>Protected reserve</span>
                    <strong>{formatInr(selected.rules.protected_cash.amount)}</strong>
                    <small>Unavailable to every scenario</small>
                  </article>
                </div>

                <div className="insight-grid">
                  <article className="panel chart-placeholder">
                    <div className="panel-head">
                      <div>
                        <span className="eyebrow">Performance</span>
                        <h3>Portfolio vs benchmark</h3>
                      </div>
                      <span className="period">1Y</span>
                    </div>
                    <div className="empty-chart" role="img" aria-label="No performance data available">
                      <div className="baseline" />
                      <p>Publish reconciled transactions to calculate performance.</p>
                    </div>
                  </article>

                  <article className="panel" id="rules">
                    <div className="panel-head">
                      <div>
                        <span className="eyebrow">Active controls</span>
                        <h3>Portfolio rules</h3>
                      </div>
                    </div>
                    <ul className="rule-list">
                      <li>
                        <span className="rule-symbol">R</span>
                        <div><strong>Reserve protected</strong><small>{formatInr(selected.rules.protected_cash.amount)} cannot be allocated</small></div>
                        <span className="rule-state">Hard</span>
                      </li>
                      <li>
                        <span className="rule-symbol">W</span>
                        <div><strong>No equal weighting</strong><small>Every allocation needs a stated method</small></div>
                        <span className="rule-state">Hard</span>
                      </li>
                      <li>
                        <span className="rule-symbol">7</span>
                        <div><strong>Weekly review</strong><small>Exception-based, not daily noise</small></div>
                        <span className="rule-state soft">Cadence</span>
                      </li>
                    </ul>
                  </article>
                </div>
              </section>

              <section className="two-column" id="data">
                <article className="panel">
                  <div className="panel-head">
                    <div>
                      <span className="eyebrow">Secure intake</span>
                      <h2>Add a data source</h2>
                    </div>
                    <span className="privacy-tag">Quarantined</span>
                  </div>
                  <p className="panel-copy">
                    Brokerage files can become ledger candidates. Research PDFs remain evidence only.
                  </p>
                  <form className="upload-form" onSubmit={uploadFile}>
                    <label>
                      <span>What does this file represent?</span>
                      <select name="source_role" defaultValue="brokerage_ledger">
                        <option value="brokerage_ledger">Brokerage transaction/tax-lot ledger</option>
                        <option value="broker_statement">Broker statement snapshot</option>
                        <option value="pms_statement">PMS statement snapshot</option>
                        <option value="research">Research evidence</option>
                      </select>
                    </label>
                    <label className="file-drop">
                      <span className="upload-arrow" aria-hidden="true">↑</span>
                      <strong>Choose PDF, XLS, XLSX, or CSV</strong>
                      <small>Maximum 50 MB · Macros are rejected</small>
                      <input name="file" type="file" accept=".pdf,.xls,.xlsx,.csv" required />
                    </label>
                    <button className="primary-button" type="submit">Check and quarantine file</button>
                  </form>

                  {upload && (
                    <div className="upload-result" role="status">
                      <div>
                        <strong>{upload.original_name}</strong>
                        <span>{upload.detected_type}</span>
                      </div>
                      <dl>
                        <div><dt>Status</dt><dd>{upload.state.replaceAll("_", " ")}</dd></div>
                        <div><dt>Authority</dt><dd>{upload.authority_level.replaceAll("_", " ")}</dd></div>
                        <div><dt>Size</dt><dd>{Math.ceil(upload.size_bytes / 1024)} KB</dd></div>
                      </dl>
                      {(upload.parser_summary.warnings ?? []).map((warning) => (
                        <p key={warning}>Review: {warning}</p>
                      ))}
                    </div>
                  )}
                </article>

                <article className="panel chat-panel" id="ask">
                  <div className="panel-head">
                    <div>
                      <span className="eyebrow">Bounded AI</span>
                      <h2>Ask Portfolio Intelligence</h2>
                    </div>
                    <span className="mode-pill small">Read-only</span>
                  </div>
                  <p className="panel-copy">
                    The agent can explain available data and limits. It cannot create numbers or place a trade.
                  </p>
                  <form className="chat-form" onSubmit={askAgent}>
                    <label className="sr-only" htmlFor="question">Question</label>
                    <textarea
                      id="question"
                      value={chatQuestion}
                      onChange={(event) => setChatQuestion(event.target.value)}
                      rows={4}
                      maxLength={4000}
                    />
                    <button className="primary-button dark" type="submit" disabled={agentRunning}>
                      {agentRunning ? "Running policy checks…" : "Run portfolio review"}
                    </button>
                  </form>
                  {agent && (
                    <div className="agent-result" aria-live="polite">
                      <div className="agent-meta">
                        <span>{agent.policy.decision?.replaceAll("_", " ")}</span>
                        <span>{agent.stages.length} bounded stages</span>
                        <span>{agent.evidence.length} evidence items</span>
                      </div>
                      <p>{agent.answer}</p>
                      {agent.limitations.length > 0 && (
                        <details>
                          <summary>Limitations and controls</summary>
                          <ul>{agent.limitations.map((item) => <li key={item}>{item}</li>)}</ul>
                        </details>
                      )}
                    </div>
                  )}
                </article>
              </section>

              <section className="create-another">
                <details>
                  <summary>Add another portfolio</summary>
                  <form className="create-form compact" onSubmit={createPortfolio}>
                    <label><span>Name</span><input name="name" required minLength={2} /></label>
                    <label>
                      <span>Type</span>
                      <select name="portfolio_type" defaultValue="self_managed">
                        <option value="self_managed">Self-managed</option>
                        <option value="pms">PMS</option>
                        <option value="model">Model</option>
                        <option value="interest">Portfolio of Interest</option>
                      </select>
                    </label>
                    <label><span>Benchmark</span><input name="benchmark_code" required defaultValue="NIFTY_500_TRI" /></label>
                    <button className="secondary-button" type="submit">Create</button>
                  </form>
                </details>
              </section>
            </>
          )}
        </section>
      </div>
    </main>
  );
}

