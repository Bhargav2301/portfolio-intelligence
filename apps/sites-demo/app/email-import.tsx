"use client";

import { FormEvent, useEffect, useState } from "react";
import type { EmailImportStatus } from "../lib/types";

async function loadStatus() {
  const response = await fetch("/api/email/preferences", { cache: "no-store" });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error ?? "Unable to load mailbox settings");
  return payload as EmailImportStatus;
}

export function EmailImportPrompt() {
  const [status, setStatus] = useState<EmailImportStatus | null>(null);
  const [email, setEmail] = useState("");
  const [consent, setConsent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    loadStatus().then(setStatus).catch(() => setStatus(null));
  }, []);

  if (!status || (status.promptStatus !== "pending" && !saved)) return null;

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const response = await fetch("/api/email/preferences", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ wealthManagerEmail: email, consent }),
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error ?? "Unable to save sender rule");
      setStatus(payload as EmailImportStatus);
      setSaved(true);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to save sender rule");
    } finally {
      setBusy(false);
    }
  }

  async function dismiss() {
    setBusy(true);
    await fetch("/api/email/preferences", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ action: "dismiss" }),
    });
    setStatus((current) => current ? { ...current, promptStatus: "dismissed" } : current);
    setBusy(false);
  }

  return (
    <div className="modal-backdrop email-prompt-backdrop" role="presentation">
      <section className="email-prompt" role="dialog" aria-modal="true" aria-labelledby="wealth-email-title">
        <span className="email-prompt-icon" aria-hidden="true">@</span>
        {!saved ? <>
          <p className="eyebrow">Optional data connection</p>
          <h2 id="wealth-email-title">Where do your portfolio statements come from?</h2>
          <p>Save the exact wealth manager email address that sends your monthly PDFs or spreadsheets. Portfolio Intelligence will never scan unrelated senders.</p>
          <form onSubmit={submit}>
            <label>Wealth manager email address<input type="email" value={email} onChange={(event) => setEmail(event.target.value)} placeholder="statements@wealthmanager.com" autoComplete="email" required /></label>
            <label className="consent-row"><input type="checkbox" checked={consent} onChange={(event) => setConsent(event.target.checked)} /><span>I authorize read-only import of supported attachments from this exact sender after I separately connect Google.</span></label>
            {error && <p className="form-error" role="alert">{error}</p>}
            <div className="dialog-actions"><button type="button" className="quiet-button" disabled={busy} onClick={() => void dismiss()}>Not now</button><button className="primary-button" disabled={!email.trim() || !consent || busy}>{busy ? "Saving…" : "Save sender"}</button></div>
          </form>
        </> : <>
          <p className="eyebrow">Sender rule saved</p>
          <h2 id="wealth-email-title">Your mailbox remains private</h2>
          <p>Only matching PDF, CSV, TSV, XLS, and XLSX attachments can be copied into private storage. Every item stays pending until it is reviewed.</p>
          <div className="email-sender-chip">{status.wealthManagerEmail}</div>
          <div className="dialog-actions">
            <button className="quiet-button" onClick={() => setSaved(false)}>Done</button>
            {status.googleConfigured && <button className="primary-button" onClick={() => { location.href = "/api/connections/google/start"; }}>Connect Google read-only</button>}
          </div>
          {!status.googleConfigured && <p className="email-config-note">Google OAuth is not active yet. The saved sender rule will be ready when the private connector credentials are added.</p>}
        </>}
      </section>
    </div>
  );
}

export function MailboxConnectionCard() {
  const [status, setStatus] = useState<EmailImportStatus | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    loadStatus().then(setStatus).catch((reason: Error) => setError(reason.message));
  }, []);

  async function sync() {
    setBusy(true);
    setError("");
    try {
      const response = await fetch("/api/email/sync", { method: "POST" });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error ?? "Mailbox sync failed");
      setStatus(payload as EmailImportStatus);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Mailbox sync failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <article className="connection-card mailbox-card">
      <div className="provider-mark google">G</div>
      <div className="connection-main">
        <div><h3>Google mailbox statements</h3><span className={`connection-status ${status?.mailboxStatus ?? "not_connected"}`}>{(status?.mailboxStatus ?? "checking").replaceAll("_", " ")}</span></div>
        <p>{status?.detail ?? "Checking the private mailbox connector…"}</p>
        {status?.wealthManagerEmail && <small>Allowed sender: {status.wealthManagerEmail}</small>}
        {status?.lastSyncedAt && <small>Last sync {new Date(status.lastSyncedAt).toLocaleString("en-IN")}</small>}
        {status && status.importedCount > 0 && <small>{status.importedCount} attachment{status.importedCount === 1 ? "" : "s"} stored · {status.pendingReviewCount} awaiting review</small>}
        {error && <small className="negative">{error}</small>}
      </div>
      <div className="connection-actions">
        {status?.mailboxStatus === "connected"
          ? <button className="primary-button" disabled={busy} onClick={() => void sync()}>{busy ? "Syncing…" : "Import matching files"}</button>
          : status?.googleConfigured && status.wealthManagerEmail
            ? <button className="primary-button" onClick={() => { location.href = "/api/connections/google/start"; }}>Connect Google</button>
            : <button className="quiet-button" disabled>Setup required</button>}
      </div>
    </article>
  );
}
