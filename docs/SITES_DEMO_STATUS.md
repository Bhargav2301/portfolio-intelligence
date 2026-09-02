# Hosted Sites demo status

Last verified: 2 September 2026

## Outcome

Portfolio Intelligence Sites version 18 is active at [portfolio-intelligence.satoshinara.chatgpt.site](https://portfolio-intelligence.satoshinara.chatgpt.site) with owner-only access. This repository contains a sanitized source snapshot in [`apps/sites-demo/`](../apps/sites-demo/) so the hosted product path can be inspected and tested without publishing account data or deployment credentials.

## Validation

| Check | Result |
|---|---|
| Optimized Sites/Vinext build and artifact validation | Pass |
| JavaScript import, hashing, and rendered-preview tests | 9 passed |
| ESLint | Pass |
| Python ingestion, policy, coordinator, and LangGraph tests | 6 passed |
| Public secret and owner-data scan | Pass for the sanitized snapshot |

## Implemented demo path

- Responsive laptop, tablet, and smartphone layout with collapsible navigation and copilot panel.
- Account-scoped manual portfolio creation and append-only transaction ledger.
- Native browser file selection for CSV, TSV, XLS, XLSX, normalized JSON, and PDF metadata registration.
- Schema inference, header aliases, non-first header rows, multi-sheet selection, numeric validation, consolidated lot flattening, reconciliation warnings, and an owner review step.
- Browser-computed SHA-256 provenance for imports and PDF registrations.
- Deterministic holdings, cost basis, value, gain/loss, allocation, concentration, evidence, and scenario calculations.
- Bounded in-session chat context using the latest eight messages and the authenticated account snapshot.
- Optional private LLM endpoint and process-isolated TradingAgents/LangGraph runtime adapters, with deterministic fail-closed fallback.
- Account-data deletion and reset-version controls; no trade-execution endpoint.

## Public sanitization boundary

The public snapshot uses invented fixtures and excludes owner holdings, quantities, prices, costs, source filenames, private-source aggregates, customer-specific ticker aliases, raw uploaded documents, runtime secrets, the live Sites project identifier, and generated Vinext font/cache artifacts. The placeholder `.openai/hosting.json` must be replaced by the Sites lifecycle before deploying a separate instance.

## Inactive integrations and remaining gates

- Sites version 18 was privately redeployed with protected environment revision 5. Portfolio chat
  uses the approved billed `google/gemma-4-26b-a4b-it` OpenRouter route. The free Gemma route
  returned provider `429` responses during the 31 August preflight, while the approved standard
  route completed successfully.
- The external Render runtime passed public health and shared-token authentication checks. The
  protected `TRADING_AGENTS_API_URL` and `TRADING_AGENTS_API_TOKEN` are active in Sites, and Agent
  Desk now uses the external TradingAgents/LangGraph bridge without committing runtime secrets.
- `z-ai/glm-5.3-flash` completed the OpenRouter preflight successfully. The legacy
  `stealth/ox-alpha` identifier is retired and redirects callers to the stable GLM identifier.
- Upstox requires its client ID, client secret, exact redirect URI, and connector-encryption key before read-only OAuth can be enabled.
- Conversation history is bounded browser-session state, not durable server-side memory across reloads or devices.
- Raw PDF/workbook storage remains blocked until private object storage, malware scanning, parser isolation, and retention/deletion controls are enabled.
- Real-money advice and order execution remain intentionally unavailable.

## GitHub merge status

- PR #4: R2/R3 evidence and analytics checkpoint; merged into `main`.
- PR #5: demo MVP agent/chat bridge; merged into `main`.
- PR #6: sanitized Sites demo and current-status sync; merged into `main`.
- The local status is based on the merged GitHub `main` history plus the activation evidence in this
  update.
