"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";

import {
  AgentResult,
  AnalyticsSnapshot,
  ExtractedRecord,
  ImportBatch,
  LedgerSnapshot,
  MonitorSnapshot,
  Portfolio,
  PublicationAccepted,
  ReconciliationCase,
  UploadCompleted,
  UploadInitiated,
  requestJson,
  requestJsonWithMetadata,
  uploadObject,
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
  const [uploading, setUploading] = useState(false);
  const [uploadName, setUploadName] = useState("");
  const [records, setRecords] = useState<ExtractedRecord[]>([]);
  const [cases, setCases] = useState<ReconciliationCase[]>([]);
  const [batch, setBatch] = useState<ImportBatch | null>(null);
  const [batchEtag, setBatchEtag] = useState<string | null>(null);
  const [includedIds, setIncludedIds] = useState<Set<string>>(new Set());
  const [excludedReasons, setExcludedReasons] = useState<Record<string, string>>({});
  const [acknowledged, setAcknowledged] = useState(false);
  const [publication, setPublication] = useState<PublicationAccepted | null>(null);
  const [agent, setAgent] = useState<AgentResult | null>(null);
  const [analytics, setAnalytics] = useState<AnalyticsSnapshot | null>(null);
  const [ledger, setLedger] = useState<LedgerSnapshot | null>(null);
  const [monitoring, setMonitoring] = useState<MonitorSnapshot | null>(null);
  const [instrument, setInstrument] = useState("");
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

  const loadIntelligence = useCallback(async (portfolioId: string) => {
    if (!portfolioId) return;
    try {
      const [analyticsResult, ledgerResult, monitorResult] = await Promise.all([
        requestJson<AnalyticsSnapshot>(`/api/core/v1/portfolios/${portfolioId}/analytics/latest`),
        requestJson<LedgerSnapshot>(`/api/core/v1/portfolios/${portfolioId}/holdings`),
        requestJson<MonitorSnapshot>(`/api/core/v1/portfolios/${portfolioId}/monitors/latest`),
      ]);
      setAnalytics(analyticsResult);
      setLedger(ledgerResult);
      setMonitoring(monitorResult);
      setInstrument((current) => current || ledgerResult.holdings[0]?.instrument_reference || "");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not load portfolio intelligence.");
    }
  }, []);

  useEffect(() => {
    void loadIntelligence(selected?.id ?? "");
  }, [loadIntelligence, selected?.id]);

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
    setNotice("Creating a checksum and secure quarantine grant…");
    setRecords([]);
    setCases([]);
    setBatch(null);
    setPublication(null);
    const form = new FormData(event.currentTarget);
    const file = form.get("file");
    if (!(file instanceof File)) {
      setError("Choose a certified CSV file.");
      return;
    }
    setUploading(true);
    try {
      const digest = await crypto.subtle.digest("SHA-256", await file.arrayBuffer());
      const sha256 = Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, "0")).join("");
      const initiated = await requestJson<UploadInitiated>("/api/core/v1/uploads", {
        method: "POST",
        body: JSON.stringify({
          portfolio_id: selected.id,
          original_name: file.name,
          source_role: "brokerage_ledger",
          content_type: "text/csv",
          size_bytes: file.size,
          sha256,
        }),
      });
      await uploadObject(initiated, file);
      setNotice("Scanning and parsing the certified ledger…");
      const completed = await requestJson<UploadCompleted>(
        `/api/core/v1/uploads/${initiated.upload_id}/complete`,
        { method: "POST", headers: { "Idempotency-Key": crypto.randomUUID() } },
      );
      const [recordResult, caseResult, batchResult] = await Promise.all([
        requestJson<ExtractedRecord[]>(`/api/core/v1/extractions/${completed.extraction_run_id}/records`),
        requestJson<ReconciliationCase[]>(`/api/core/v1/import-batches/${completed.import_batch_id}/reconciliation-cases`),
        requestJsonWithMetadata<ImportBatch>(`/api/core/v1/import-batches/${completed.import_batch_id}`),
      ]);
      setUploadName(file.name);
      setRecords(recordResult);
      setIncludedIds(new Set(recordResult.map((record) => record.id)));
      setCases(caseResult);
      setBatch(batchResult.data);
      setBatchEtag(batchResult.etag);
      setNotice("Quarantine checks completed. Review every row before validation.");
    } catch (caught) {
      setNotice("");
      setError(caught instanceof Error ? caught.message : "File could not be accepted.");
    } finally {
      setUploading(false);
    }
  }

  function toggleRecord(recordId: string, include: boolean) {
    setIncludedIds((current) => {
      const next = new Set(current);
      if (include) next.add(recordId); else next.delete(recordId);
      return next;
    });
    setExcludedReasons((current) => {
      const next = { ...current };
      if (include) delete next[recordId];
      else next[recordId] = next[recordId] || "Excluded by the portfolio owner during review.";
      return next;
    });
    setAcknowledged(false);
  }

  async function resolveCase(item: ReconciliationCase) {
    setError("");
    try {
      const resolved = await requestJson<ReconciliationCase>(
        `/api/core/v1/reconciliation-cases/${item.id}/resolve`,
        {
          method: "POST",
          body: JSON.stringify({
            resolution: "exclude",
            reason: "The owner reviewed and explicitly excluded this unmapped input from R1 publication.",
          }),
        },
      );
      setCases((current) => current.map((candidate) => candidate.id === resolved.id ? resolved : candidate));
      setNotice("Reconciliation decision recorded in the audit trail.");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The reconciliation case could not be resolved.");
    }
  }

  async function validateBatch() {
    if (!batch || !batchEtag) return;
    setError("");
    try {
      const result = await requestJsonWithMetadata<ImportBatch>(
        `/api/core/v1/import-batches/${batch.id}/validate`,
        {
          method: "POST",
          headers: { "If-Match": batchEtag, "Idempotency-Key": crypto.randomUUID() },
          body: JSON.stringify({
            included_record_ids: [...includedIds],
            excluded_records: excludedReasons,
          }),
        },
      );
      setBatch(result.data);
      setBatchEtag(result.etag);
      setAcknowledged(false);
      setNotice("Validation passed. Owner acknowledgment and recent MFA are required to publish.");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Batch validation failed.");
    }
  }

  async function publishBatch() {
    if (!batch || !batchEtag || !batch.validated_hash || !acknowledged) return;
    setError("");
    try {
      const result = await requestJson<PublicationAccepted>(
        `/api/core/v1/import-batches/${batch.id}/publish`,
        {
          method: "POST",
          headers: { "If-Match": batchEtag, "Idempotency-Key": crypto.randomUUID() },
          body: JSON.stringify({
            included_record_ids: [...includedIds],
            excluded_records: excludedReasons,
            validated_hash: batch.validated_hash,
            acknowledgment: "I reviewed this batch and authorize immutable ledger publication.",
          }),
        },
      );
      setPublication(result);
      setBatch((current) => current ? { ...current, state: "published", published_ledger_version: result.ledger_version } : current);
      setNotice(`Ledger version ${result.ledger_version} was published atomically.`);
      await loadIntelligence(selected.id);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Ledger publication failed.");
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
          instrument: instrument || undefined,
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
                    setUploadName("");
                    setRecords([]);
                    setCases([]);
                    setBatch(null);
                    setBatchEtag(null);
                    setIncludedIds(new Set());
                    setExcludedReasons({});
                    setPublication(null);
                    setAgent(null);
                    setAnalytics(null);
                    setLedger(null);
                    setMonitoring(null);
                    setInstrument("");
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
              <section className={`quality-banner ${analytics?.quality_state === "trusted" ? "trusted" : ""}`} aria-label="Portfolio data status">
                <div className="quality-icon" aria-hidden="true">{analytics?.quality_state === "trusted" ? "✓" : "!"}</div>
                <div>
                  <strong>Portfolio data is {analytics?.quality_state ?? "loading"}</strong>
                  <p>
                    {analytics?.quality_state === "trusted"
                      ? `Ledger version ${analytics.ledger_version} is authoritative; market-history metrics remain separately gated.`
                      : "No approved ledger has been published. AI analysis is limited until reconciliation."}
                  </p>
                </div>
                <a href="#data">Add or review data</a>
              </section>

              <section id="overview" aria-labelledby="overview-title">
                <div className="section-heading horizontal">
                  <div>
                    <span className="eyebrow">
                      {analytics ? `As of ${new Date(analytics.as_of).toLocaleString("en-IN")}` : "Loading snapshot"}
                    </span>
                    <h2 id="overview-title">Portfolio overview</h2>
                  </div>
                  <span className="status-text"><i aria-hidden="true" /> {monitoring?.state ?? "Loading"}</span>
                </div>

                <div className="metric-grid">
                  <article className="metric-card">
                    <span>Current value</span>
                    <strong>{formatInr(analytics?.metrics.current_value)}</strong>
                    <small>{ledger ? `${ledger.holdings.length} published holding(s)` : "Waiting for ledger"}</small>
                  </article>
                  <article className="metric-card">
                    <span>Net invested</span>
                    <strong>{formatInr(analytics?.metrics.net_invested_capital)}</strong>
                    <small>Net external cash events</small>
                  </article>
                  <article className="metric-card">
                    <span>Cash balance</span>
                    <strong>{formatInr(analytics?.metrics.cash_balance)}</strong>
                    <small>{formatInr(ledger?.available_cash)} available after reserve</small>
                  </article>
                  <article className="metric-card protected">
                    <span>Protected reserve</span>
                    <strong>{formatInr(selected.rules.protected_cash.amount)}</strong>
                    <small>Unavailable to every scenario</small>
                  </article>
                </div>

                <div className="insight-grid">
                  <article className="panel" id="holdings">
                    <div className="panel-head">
                      <div>
                        <span className="eyebrow">Authoritative ledger</span>
                        <h3>Holdings</h3>
                      </div>
                      <span className="period">v{ledger?.ledger_version ?? 0}</span>
                    </div>
                    {ledger && ledger.holdings.length > 0 ? (
                      <div className="table-scroll">
                        <table className="holdings-table">
                          <thead><tr><th>Instrument</th><th>Quantity</th><th>Value</th><th>Weight</th><th>Unrealized P/L</th></tr></thead>
                          <tbody>{ledger.holdings.map((holding) => (
                            <tr key={holding.instrument_reference}>
                              <th>{holding.instrument_reference}</th>
                              <td>{Number(holding.quantity).toLocaleString("en-IN")}</td>
                              <td>{formatInr(holding.market_value)}</td>
                              <td>{holding.weight_percent ? `${holding.weight_percent}%` : "—"}</td>
                              <td>{formatInr(holding.unrealized_pnl)}</td>
                            </tr>
                          ))}</tbody>
                        </table>
                      </div>
                    ) : (
                      <div className="empty-chart" role="status"><p>Publish reconciled ledger events to calculate holdings.</p></div>
                    )}
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

              <section className="panel monitor-panel" id="monitors" aria-labelledby="monitor-title">
                <div className="panel-head">
                  <div>
                    <span className="eyebrow">Automated, deterministic checks</span>
                    <h2 id="monitor-title">Portfolio monitors</h2>
                  </div>
                  <span className={`monitor-state ${monitoring?.state ?? ""}`}>{monitoring?.state ?? "Loading"}</span>
                </div>
                {monitoring && monitoring.alerts.length > 0 ? (
                  <div className="alert-grid">{monitoring.alerts.map((item) => (
                    <article className={`monitor-alert ${item.severity}`} key={item.id}>
                      <span>{item.kind.replaceAll("_", " ")}</span>
                      <strong>{item.title}</strong>
                      <p>{item.detail}</p>
                      {item.observed_value && <small>Observed {item.observed_value} · Threshold {item.threshold_value}</small>}
                    </article>
                  ))}</div>
                ) : (
                  <p className="panel-copy">No rule breach is present in the latest published snapshot.</p>
                )}
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
                    R1 accepts only the certified <code>spi-ledger-csv/v1</code> format. Files remain
                    quarantined until every row is reviewed and an owner publishes with recent MFA.
                  </p>
                  <form className="upload-form" onSubmit={uploadFile}>
                    <label className="file-drop">
                      <span className="upload-arrow" aria-hidden="true">↑</span>
                      <strong>Choose a certified ledger CSV</strong>
                      <small>Maximum 50 MB · SHA-256 verified · formula cells rejected</small>
                      <input name="file" type="file" accept=".csv,text/csv" required />
                    </label>
                    <button className="primary-button" type="submit" disabled={uploading}>
                      {uploading ? "Checking quarantine…" : "Securely upload and reconcile"}
                    </button>
                  </form>

                  {batch && (
                    <div className="reconciliation-workbench" aria-live="polite">
                      <div className="workbench-summary">
                        <div><span>Source</span><strong>{uploadName}</strong></div>
                        <div><span>Batch state</span><strong>{batch.state.replaceAll("_", " ")}</strong></div>
                        <div><span>Base ledger</span><strong>v{batch.base_ledger_version}</strong></div>
                        <div><span>Rows</span><strong>{records.length}</strong></div>
                      </div>

                      {cases.length > 0 && (
                        <div className="case-list">
                          <h3>Reconciliation exceptions</h3>
                          {cases.map((item) => (
                            <div className={`case-item ${item.state}`} key={item.id}>
                              <div>
                                <strong>{item.kind.replaceAll("_", " ")}</strong>
                                <small>{String(item.details.message ?? "Manual decision required.")}</small>
                              </div>
                              {item.state === "open" ? (
                                <button className="secondary-button" type="button" onClick={() => void resolveCase(item)}>
                                  Exclude and audit
                                </button>
                              ) : <span>Resolved</span>}
                            </div>
                          ))}
                        </div>
                      )}

                      <div className="table-scroll">
                        <table className="reconciliation-table">
                          <caption>Normalized records with source-row lineage and inclusion decisions</caption>
                          <thead><tr>
                            <th>Include</th><th>Row</th><th>Event</th><th>Instrument</th>
                            <th>Quantity</th><th>Price</th><th>Cash delta</th><th>Confidence</th>
                          </tr></thead>
                          <tbody>{records.map((record) => {
                            const included = includedIds.has(record.id);
                            return (
                              <tr key={record.id} className={included ? "" : "excluded-row"}>
                                <td><input
                                  type="checkbox"
                                  checked={included}
                                  onChange={(event) => toggleRecord(record.id, event.target.checked)}
                                  aria-label={`Include source row ${record.source_row}`}
                                  disabled={batch.state === "published"}
                                /></td>
                                <td>{record.source_row}</td>
                                <td>{String(record.normalized_data.event_type ?? "—")}</td>
                                <td>{String(record.normalized_data.symbol ?? record.normalized_data.instrument_id ?? "—")}</td>
                                <td>{String(record.normalized_data.quantity ?? "—")}</td>
                                <td>{String(record.normalized_data.price ?? "—")}</td>
                                <td>{String(record.normalized_data.cash_delta ?? "—")}</td>
                                <td>{String(record.confidence)}</td>
                              </tr>
                            );
                          })}</tbody>
                        </table>
                      </div>

                      {Object.keys(excludedReasons).map((recordId) => (
                        <label className="exclusion-reason" key={recordId}>
                          <span>Reason for excluding row {records.find((item) => item.id === recordId)?.source_row}</span>
                          <input
                            value={excludedReasons[recordId]}
                            minLength={4}
                            onChange={(event) => setExcludedReasons((current) => ({ ...current, [recordId]: event.target.value }))}
                            disabled={batch.state === "published"}
                          />
                        </label>
                      ))}

                      {batch.state === "draft" && (
                        <button
                          className="primary-button"
                          type="button"
                          onClick={() => void validateBatch()}
                          disabled={cases.some((item) => item.state === "open") || includedIds.size === 0}
                        >
                          Validate reviewed selection
                        </button>
                      )}

                      {batch.state === "approved" && (
                        <div className="publication-review">
                          <label>
                            <input
                              type="checkbox"
                              checked={acknowledged}
                              onChange={(event) => setAcknowledged(event.target.checked)}
                            />
                            <span>I reviewed this batch and authorize immutable ledger publication.</span>
                          </label>
                          <button className="primary-button dark" type="button" disabled={!acknowledged} onClick={() => void publishBatch()}>
                            Publish immutable ledger version
                          </button>
                          <a href="/api/auth/login?step_up=1&return_to=%2F%23data">Refresh MFA before publication</a>
                        </div>
                      )}

                      {publication && (
                        <div className="publication-receipt" role="status">
                          <strong>Ledger v{publication.ledger_version} published</strong>
                          <span>Batch {publication.import_batch_id}</span>
                          <span>Audit receipt {publication.audit_event_id}</span>
                          <span>Agents remain proposal-only; no order was created.</span>
                        </div>
                      )}
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
                    <label>
                      <span>Security focus (optional)</span>
                      <select value={instrument} onChange={(event) => setInstrument(event.target.value)}>
                        <option value="">Portfolio-wide review</option>
                        {(ledger?.holdings ?? []).map((holding) => (
                          <option key={holding.instrument_reference} value={holding.instrument_reference}>
                            {holding.instrument_reference}
                          </option>
                        ))}
                      </select>
                    </label>
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
                      {agent.proposal.title && (
                        <section className="proposal-card" aria-label="Review proposal">
                          <span>{agent.proposal.status?.replaceAll("_", " ")}</span>
                          <strong>{agent.proposal.title}</strong>
                          <small>Proposal only · execution capability: {agent.proposal.can_execute ? "enabled" : "disabled"}</small>
                        </section>
                      )}
                      {agent.evidence.length > 0 && (
                        <details>
                          <summary>Evidence ({agent.evidence.length})</summary>
                          <ul>{agent.evidence.map((item, index) => (
                            <li key={String(item.id ?? index)}>
                              <a href={"/api/core" + String(item.uri ?? "")} target="_blank">
                                {String(item.title ?? item.id ?? "Evidence")}
                              </a>
                            </li>
                          ))}</ul>
                        </details>
                      )}
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

