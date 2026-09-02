# Hosted Sites demo status

Last verified: 2 September 2026

## Outcome

Portfolio Intelligence Sites version 21 is active at [portfolio-intelligence.satoshinara.chatgpt.site](https://portfolio-intelligence.satoshinara.chatgpt.site) with owner-only access. This repository contains a sanitized source snapshot in [`apps/sites-demo/`](../apps/sites-demo/) so the hosted product path can be inspected and tested without publishing account data or deployment credentials.

## Validation

| Check | Result |
|---|---|
| Optimized Sites/Vinext build and artifact validation | Pass |
| JavaScript import, hashing, and rendered-preview tests | 9 passed |
| ESLint | Pass |
| Python ingestion, policy, coordinator, LangGraph, and TradingAgents adapter tests | 9 passed |
| TypeScript and responsive browser verification | Pass |
| Gemma trusted-web invocation for the Timex/Coforge quarterly comparison | Pass; 8 citations returned from official issuer domains |
| Public secret and owner-data scan | Pass for the sanitized snapshot |

## Implemented demo path

- Responsive laptop, tablet, and smartphone layout with collapsible navigation and copilot panel.
- Account-scoped manual portfolio creation and append-only transaction ledger.
- Native browser file selection for CSV, TSV, XLS, XLSX, normalized JSON, and PDF metadata registration.
- Schema inference, header aliases, non-first header rows, multi-sheet selection, numeric validation, consolidated lot flattening, reconciliation warnings, and an owner review step.
- Browser-computed SHA-256 provenance for imports and PDF registrations.
- Deterministic holdings, cost basis, value, gain/loss, allocation, concentration, evidence, and scenario calculations.
- Bounded in-session chat context using the latest eight messages and the authenticated account snapshot.
- Full dark research workspace plus compact chat access on every other product surface.
- Portfolio, allowlisted live-web, and linked TradingAgents modes with KPI cards, deterministic tables/charts, and source cards.
- Live Research now requires a trusted-web invocation, resolves relative periods from the runtime date, and fails visibly when no allowlisted citation is returned.
- TradingAgents runtime `0.3.1` parses the upstream rendered rating, executive summary, thesis, trader action, and trader reasoning instead of expecting an object that the pinned library does not return.
- First-login exact wealth-manager sender prompt and a Gmail read-only consent/import contract.
- Private R2 staging for matching PDF and spreadsheet attachments with review-before-use status.
- Optional private LLM endpoint and process-isolated TradingAgents/LangGraph runtime adapters, with deterministic fail-closed fallback.
- Account-data deletion and reset-version controls; no trade-execution endpoint.

## Public sanitization boundary

The public snapshot uses invented fixtures and excludes owner holdings, quantities, prices, costs, source filenames, private-source aggregates, customer-specific ticker aliases, raw uploaded documents, OAuth/runtime secrets, and generated Vinext font/cache artifacts. The non-secret `.openai/hosting.json` project ID keeps this source reproducibly bound to the existing owner-only Site and must be replaced through the Sites lifecycle before deploying a separate instance.

## Inactive integrations and remaining gates

- Sites version 21 was privately redeployed with protected environment revision 6 after the
  protected chat credential was revalidated. Portfolio chat
  uses the approved billed `google/gemma-4-26b-a4b-it` OpenRouter route. The free Gemma route
  returned provider `429` responses during the 31 August preflight, while the approved standard
  route completed successfully.
- The external Render runtime passed public health and shared-token authentication checks. The
  protected `TRADING_AGENTS_API_URL` and `TRADING_AGENTS_API_TOKEN` are active in Sites, and Agent
  Desk now uses the external TradingAgents/LangGraph bridge without committing runtime secrets.
- `z-ai/glm-5.3-flash` completed the OpenRouter preflight successfully. The legacy
  `stealth/ox-alpha` identifier is retired and redirects callers to the stable GLM identifier.
- Google mailbox intake requires its OAuth client ID, protected client secret, exact callback URI, and connector-encryption key before the dormant connection button becomes active. Gmail read-only is a restricted scope and remains owner-test-only until Google's production verification gates are met.
- Upstox requires its client ID, client secret, exact redirect URI, and connector-encryption key before read-only OAuth can be enabled.
- Conversation history is bounded browser-session state, not durable server-side memory across reloads or devices.
- Raw mailbox attachments are private R2 review candidates; malware scanning and parser isolation remain required before their contents can become portfolio truth.
- Real-money advice and order execution remain intentionally unavailable.

## GitHub merge status

- PR #4: R2/R3 evidence and analytics checkpoint; merged into `main`.
- PR #5: demo MVP agent/chat bridge; merged into `main`.
- PR #6: sanitized Sites demo and current-status sync; merged into `main`.
- The local status is based on the merged GitHub `main` history plus the activation evidence in this
  update.
