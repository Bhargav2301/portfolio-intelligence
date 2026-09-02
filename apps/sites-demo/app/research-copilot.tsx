"use client";

import { FormEvent, Fragment, useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import type { ChatPresentation, ChatResponse, DashboardData } from "../lib/types";

type ChatMode = "portfolio" | "research" | "agent";
type ChatMessage = {
  role: "assistant" | "user";
  text: string;
  response?: ChatResponse;
  citedSymbols?: string[];
};

const inr = new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", notation: "compact", maximumFractionDigits: 1 });

export function ResearchCopilot({ data, agentRunId, embedded = false }: {
  data: DashboardData;
  agentRunId: string | null;
  embedded?: boolean;
}) {
  const [prompt, setPrompt] = useState("");
  const [busy, setBusy] = useState(false);
  const [mode, setMode] = useState<ChatMode>(embedded ? "research" : "portfolio");
  const [collapsed, setCollapsed] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const streamRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (embedded) return;
    const media = window.matchMedia("(max-width: 1000px)");
    const update = () => setCollapsed(media.matches);
    update();
    media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, [embedded]);

  useEffect(() => {
    streamRef.current?.scrollTo({ top: streamRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, busy]);

  async function ask(value: string) {
    const clean = value.trim();
    if (!clean || busy || (mode === "agent" && !agentRunId)) return;
    const history = messages.slice(-8).map((message) => ({ role: message.role, content: message.text }));
    setMessages((current) => [...current, { role: "user", text: clean }]);
    setPrompt("");
    setBusy(true);
    try {
      const response = await fetch(mode === "agent" ? "/api/agents/chat" : "/api/chat", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(mode === "agent"
          ? { prompt: clean, runId: agentRunId }
          : { prompt: clean, history, webResearch: mode === "research" }),
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error ?? "Unable to answer");
      if (mode === "agent") {
        const answer = payload as { answer: string; cited_symbols?: string[] };
        setMessages((current) => [...current, { role: "assistant", text: answer.answer, citedSymbols: answer.cited_symbols }]);
      } else {
        const answer = payload as ChatResponse;
        setMessages((current) => [...current, { role: "assistant", text: answer.answer, response: answer }]);
      }
    } catch (reason) {
      setMessages((current) => [...current, {
        role: "assistant",
        text: reason instanceof Error ? reason.message : "The answer could not be prepared.",
      }]);
    } finally {
      setBusy(false);
    }
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    void ask(prompt);
  }

  const suggestions = mode === "agent"
    ? ["Summarize the latest run", "Why did the agents choose this rating?", "Which policy checks applied?"]
    : mode === "research"
      ? ["What is the latest official news for my largest holding?", "Find recent exchange filings for my portfolio", "How is my portfolio positioned versus current market themes?"]
      : ["What drives my returns?", "Show concentration risk", "Organize my holdings into a table"];

  return (
    <aside className={`${embedded ? "copilot copilot-workspace" : "copilot"}${collapsed ? " collapsed" : ""}`}>
      <div className="copilot-heading">
        <div><span className="copilot-mark">PI</span><div><strong>Portfolio Intelligence</strong><small><i /> Private research workspace</small></div></div>
        {!embedded && <button className="copilot-toggle" onClick={() => setCollapsed((current) => !current)} aria-expanded={!collapsed} aria-label={collapsed ? "Open research copilot" : "Collapse research copilot"}>{collapsed ? "↑" : "↓"}</button>}
      </div>

      <div className="copilot-modes" aria-label="Research mode">
        <button className={mode === "portfolio" ? "active" : ""} onClick={() => setMode("portfolio")}><span>Portfolio</span><small>Account data</small></button>
        <button className={mode === "research" ? "active" : ""} onClick={() => setMode("research")}><span>Live research</span><small>Trusted web</small></button>
        <button className={mode === "agent" ? "active" : ""} onClick={() => setMode("agent")}><span>Agent desk</span><small>{agentRunId ? "Run linked" : "Start a run"}</small></button>
      </div>

      <div className="chat-stream" ref={streamRef}>
        {messages.length === 0 && <ChatWelcome data={data} mode={mode} embedded={embedded} onAsk={ask} />}
        {messages.map((message, index) => (
          <div className={`chat-message ${message.role}`} key={`${message.role}-${index}`}>
            {message.role === "assistant" && <span className="chat-avatar">PI</span>}
            <div className="chat-message-body">
              <AnswerText text={message.text} suppressTables={Boolean(message.response?.presentation?.table)} />
              {message.response?.presentation && <StructuredAnswer presentation={message.response.presentation} />}
              {message.response && <AnswerSources response={message.response} />}
              {message.citedSymbols && message.citedSymbols.length > 0 && <div className="chat-sources">{message.citedSymbols.map((symbol) => <span key={symbol}>{symbol} · TradingAgents artifact</span>)}</div>}
              {message.response && <div className="answer-meta">
                <span>{message.response.engine === "llm" ? `${message.response.model ?? "LLM"}` : message.response.engine === "deterministic-fallback" ? "Portfolio fallback" : "Portfolio policy"}</span>
                <span>{message.response.researchMode === "trusted-web" ? "Trusted web enabled" : "Account context"}</span>
                {message.response.fallbackReason && <span title={message.response.fallbackReason}>AI fallback · {message.response.fallbackReason}</span>}
              </div>}
            </div>
          </div>
        ))}
        {busy && <div className="chat-message assistant"><span className="chat-avatar">PI</span><div className="thinking" aria-label="Researching"><i /><i /><i /></div></div>}
      </div>

      {messages.length > 0 && <div className="suggestion-list">{suggestions.map((suggestion) => <button key={suggestion} onClick={() => void ask(suggestion)}>{suggestion}</button>)}</div>}
      <form className="chat-input" onSubmit={submit}>
        <button type="button" className="composer-plus" aria-label="Add context" title="Use Research to register PDFs and mailbox statements">+</button>
        <textarea rows={1} value={prompt} onChange={(event) => setPrompt(event.target.value)} placeholder={mode === "agent" ? "Ask about a completed TradingAgents run…" : mode === "research" ? "Ask your portfolio and the trusted web…" : "Ask about this portfolio…"} aria-label="Ask Portfolio Intelligence" onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); event.currentTarget.form?.requestSubmit(); } }} />
        <span className="composer-mode">{mode === "research" ? "Web" : mode === "agent" ? "Agents" : "Portfolio"}</span>
        <button className="composer-send" disabled={!prompt.trim() || busy || (mode === "agent" && !agentRunId)} aria-label="Send question">↑</button>
      </form>
      <p className="copilot-disclaimer">{mode === "agent" && !agentRunId ? "Start an Agent desk run to enable agent Q&A." : "Source-backed research · read-only · not investment advice."}</p>
    </aside>
  );
}

function ChatWelcome({ data, mode, embedded, onAsk }: { data: DashboardData; mode: ChatMode; embedded: boolean; onAsk: (value: string) => Promise<void> }) {
  return (
    <section className="chat-welcome">
      <span className="welcome-orbit" aria-hidden="true"><i /><i /><i /></span>
      <p>{mode === "agent" ? "TradingAgents workspace" : mode === "research" ? "Portfolio + trusted internet research" : "Authenticated portfolio intelligence"}</p>
      <h2>{embedded ? `What would you like to understand about ${data.portfolio.name}?` : "Ask about your portfolio"}</h2>
      <span>{mode === "research" ? "Live questions are searched only across the configured regulator, exchange, fund-industry, and trusted-news allowlist." : mode === "agent" ? "Run the analyst, debate, trader, and risk graph in Agent desk, then question its completed artifacts here." : "Answers use holdings, transactions, tracked snapshots, and reviewed evidence from this account."}</span>
      {embedded && <div className="welcome-actions">{(mode === "research" ? ["Latest filing for my largest holding", "Compare concentration with current market risks"] : mode === "agent" ? ["Summarize the latest run", "Explain the risk manager decision"] : ["Show my return drivers", "Build a concentration table"]).map((item) => <button key={item} onClick={() => void onAsk(item)}>{item}<b>↗</b></button>)}</div>}
    </section>
  );
}

function AnswerText({ text, suppressTables = false }: { text: string; suppressTables?: boolean }) {
  return <div className="answer-copy">{text.split(/\n+/).filter((line) => line.trim() && !(suppressTables && line.trim().startsWith("|"))).map((line, index) => {
    const heading = line.match(/^#{1,3}\s+(.+)/);
    if (heading) return <h3 key={index}>{renderInlineLinks(heading[1])}</h3>;
    const bullet = line.match(/^[-*]\s+(.+)/);
    if (bullet) return <p className="answer-bullet" key={index}><span>•</span>{renderInlineLinks(bullet[1])}</p>;
    return <p key={index}>{renderInlineLinks(line)}</p>;
  })}</div>;
}

function renderInlineLinks(value: string) {
  const expression = /\[([^\]]+)\]\((https:\/\/[^\s)]+)\)|\*\*([^*]+)\*\*/g;
  const parts: ReactNode[] = [];
  let cursor = 0;
  let match: RegExpExecArray | null;
  while ((match = expression.exec(value))) {
    if (match.index > cursor) parts.push(value.slice(cursor, match.index));
    parts.push(match[1]
      ? <a href={match[2]} target="_blank" rel="noreferrer" key={`${match.index}-${match[2]}`}>{match[1]}</a>
      : <strong key={`${match.index}-strong`}>{match[3]}</strong>);
    cursor = match.index + match[0].length;
  }
  if (cursor < value.length) parts.push(value.slice(cursor));
  return parts.map((part, index) => <Fragment key={index}>{part}</Fragment>);
}

function StructuredAnswer({ presentation }: { presentation: ChatPresentation }) {
  return (
    <div className="structured-answer">
      <h3>{presentation.title}</h3>
      {presentation.kpis.length > 0 && <div className="answer-kpis">{presentation.kpis.map((kpi) => <article key={kpi.label}><span>{kpi.label}</span><strong className={kpi.tone}>{kpi.value}</strong><small>{kpi.detail}</small></article>)}</div>}
      {presentation.chart && <AnswerChart chart={presentation.chart} />}
      {presentation.table && <div className="answer-table"><div><strong>{presentation.table.title}</strong><span>{presentation.table.rows.length} rows</span></div><div className="table-scroll"><table><thead><tr>{presentation.table.columns.map((column) => <th key={column}>{column}</th>)}</tr></thead><tbody>{presentation.table.rows.map((row, rowIndex) => <tr key={rowIndex}>{row.map((cell, cellIndex) => <td key={cellIndex}>{cell}</td>)}</tr>)}</tbody></table></div></div>}
      {presentation.note && <p className="answer-note">{presentation.note}</p>}
    </div>
  );
}

function AnswerChart({ chart }: { chart: NonNullable<ChatPresentation["chart"]> }) {
  const values = chart.series.flatMap((series) => series.values).filter((value): value is number => value !== null && Number.isFinite(value));
  const maximum = Math.max(1, ...values.map((value) => Math.abs(value)));
  if (chart.type === "line") {
    const series = chart.series[0];
    const present = series.values.map((value) => value ?? 0);
    const min = Math.min(...present);
    const max = Math.max(...present);
    const path = present.map((value, index) => {
      const x = 14 + (index / Math.max(1, present.length - 1)) * 472;
      const y = 138 - ((value - min) / Math.max(1, max - min)) * 104;
      return `${index ? "L" : "M"}${x.toFixed(1)},${y.toFixed(1)}`;
    }).join(" ");
    return <figure className="answer-chart line"><figcaption><strong>{chart.title}</strong><span>{series.name}</span></figcaption><svg viewBox="0 0 500 168" role="img" aria-label={chart.title}>{[34, 86, 138].map((y) => <line key={y} x1="14" x2="486" y1={y} y2={y} />)}<path d={path} /><text x="14" y="162">{chart.categories[0]}</text><text x="486" y="162" textAnchor="end">{chart.categories.at(-1)}</text></svg></figure>;
  }
  return <figure className="answer-chart bars"><figcaption><strong>{chart.title}</strong><span>{chart.series[0]?.name}</span></figcaption><div>{chart.categories.map((category, index) => {
    const value = chart.series[0]?.values[index] ?? 0;
    const label = chart.unit === "currency" ? inr.format(value) : chart.unit === "percent" ? `${value.toFixed(1)}%` : value.toFixed(1);
    return <div className="answer-bar" key={category}><span>{category}</span><i><b className={value < 0 ? "negative" : ""} style={{ width: `${Math.max(2, Math.abs(value) / maximum * 100)}%` }} /></i><strong>{label}</strong></div>;
  })}</div></figure>;
}

function AnswerSources({ response }: { response: ChatResponse }) {
  const sources = useMemo(() => [
    ...response.citations.map((citation) => ({ id: citation.url, title: citation.title, label: citation.domain, url: citation.url })),
    ...response.evidence.map((evidence) => ({ id: evidence.id, title: evidence.title, label: `${evidence.symbol} · ${evidence.publisher}`, url: evidence.sourceUri })),
  ].filter((source, index, items) => items.findIndex((item) => item.url === source.url) === index), [response]);
  if (!sources.length) return null;
  return <div className="answer-sources"><div><strong>Sources</strong><span>{sources.length}</span></div>{sources.slice(0, 8).map((source, index) => <a href={source.url} target="_blank" rel="noreferrer" key={source.id}><b>{index + 1}</b><span><strong>{source.title}</strong><small>{source.label}</small></span><i>↗</i></a>)}</div>;
}
