# Portfolio Intelligence — Sites test application

This is the hosted V1 test surface for Portfolio Intelligence's Branch C
architecture: deterministic portfolio analytics with an evidence-gated
conversational layer.

## Public snapshot boundary

This directory is a sanitized source snapshot for the public repository. It uses
synthetic fixtures and excludes owner portfolio names, source filenames,
positions, costs, private-source aggregates, customer-specific ticker aliases,
runtime credentials, and the live Sites project identifier. Generated Vinext
font/cache artifacts are also omitted and are recreated by the locked build.

Before using this snapshot with Sites, initialize or edit the Site through the
Sites lifecycle so `.openai/hosting.json` contains the actual project identifier.
Never commit production environment values; configure them in the hosting
environment.

## V1 test boundary

- D1-backed, per-user portfolio and append-only transaction ledger
- First-run wealth-manager sender prompt, manual setup, canonical CSV / normalized JSON import, and read-only OAuth contracts
- Source-hashed import batches, normalized rows, and preserved acquisition lots
- Buy and sell validation with explicit confirmation before persistence
- Reversal events instead of destructive transaction edits
- Deterministic holdings, cost basis, valuation, allocation, and what-if math
- Source-tiered evidence records, private R2 document staging, and content hashes
- Research copilot with portfolio, allowlisted live-web, and TradingAgents modes
- Structured answers with KPI cards, deterministic tables, charts, and linked citations
- Exact-sender Gmail read-only attachment intake with explicit consent and review-before-use status
- Fail-closed response to personalized buy, sell, or hold requests
- Responsive overview, research, activity, scenario, accounts, and agent surfaces

Demo portfolio data has been removed. Manual prices remain user-provided until
updated; the Upstox connector becomes active only after production credentials
are configured. The application does not provide investment advice or execute
trades.

## Architecture

- Next.js-compatible application built with Vinext
- Cloudflare Worker runtime
- Cloudflare D1-compatible persistence
- Drizzle schema and migration artifacts
- Platform-provided authenticated-user headers for tenant ownership when present

The production finance-domain API remains in the main GitHub repository. This
Sites application provides the first deployable product interface and validates
the same core boundaries in a serverless test environment.

## Prerequisites

- Node.js `>=22.13.0`
- Linux with `flock`, `curl`, and GNU `timeout`

The independently deployed agent runtime requires Python 3.12, Git, its locked
Python dependencies, a long internal bearer token, and one selected LLM provider
credential. See `docs/langgraph-deployment-credentials.md` for the complete
conditional credential and infrastructure matrix.

## Sites Lifecycle

The Sites lifecycle CLI runs the locked dependency install before returning this checkout. Edit the source under `app/`, then checkpoint when a coherent milestone is ready to inspect or share. The remote Sites builder runs `npm run build` against the pushed commit. Do not repeat install or build as a normal pre-checkpoint step.

This starter does not use `wrangler.jsonc`.

`install:ci` is intentionally a single, non-retrying `npm ci`. It refuses a concurrent install for the same project, consumes a matching image-seeded npm cache with `--prefer-offline` while retaining registry fallback for a missing cache object, otherwise downloads and verifies the complete vinext tarball recorded in `package-lock.json`, limits npm to one socket, and terminates a stalled install. `build` applies a short timeout and then validates the Sites artifact. These helpers target Linux and use GNU `timeout`; they are not native macOS scripts.

Scripts that need writable project-scoped home, npm, XDG, and temporary paths use `scripts/sites-env.sh`. The `dev` and `start` scripts honor the caller's runtime environment and keep Wrangler logs inside the checkout. The generated `.sites-runtime/` directory is disposable and ignored by Git.

## Project shape

- product UI and API routes under `app/`
- `app/chatgpt-auth.ts` provides optional dispatch-owned ChatGPT sign-in helpers
- `.openai/hosting.json` is a public placeholder for the Sites binding manifest
- `vite.config.ts` simulates declared bindings for local development
- `db/index.ts` reads the D1 binding from the Cloudflare Worker environment
- `db/schema.ts` defines portfolio, ledger, price, evidence, mailbox, and tracked-snapshot records
- `DOCUMENTS` is the private R2 binding for mailbox attachment staging
- `drizzle/` contains the deployable D1 migration
- `drizzle.config.ts` supports local migration generation when needed

## Workspace Auth Headers

OpenAI workspace sites can read the current user's email from
`oai-authenticated-user-email`.

SIWC-authenticated workspace sites may also receive
`oai-authenticated-user-full-name` when the user's SIWC profile has a non-empty
`name` claim. The full-name value is percent-encoded UTF-8 and is accompanied by
`oai-authenticated-user-full-name-encoding: percent-encoded-utf-8`.

Treat the full name as optional and fall back to email when it is absent:

```tsx
import { headers } from "next/headers";

export default async function Home() {
  const requestHeaders = await headers();
  const email = requestHeaders.get("oai-authenticated-user-email");
  const encodedFullName = requestHeaders.get("oai-authenticated-user-full-name");
  const fullName =
    encodedFullName &&
    requestHeaders.get("oai-authenticated-user-full-name-encoding") ===
      "percent-encoded-utf-8"
      ? decodeURIComponent(encodedFullName)
      : null;

  const displayName = fullName ?? email;
  // ...
}
```

## Optional Dispatch-Owned ChatGPT Sign-In

Import the ready-to-use helpers from `app/chatgpt-auth.ts` when the site needs
optional or required ChatGPT sign-in:

- Use `getChatGPTUser()` for optional signed-in UI.
- Use `requireChatGPTUser(returnTo)` for server-rendered pages that should send
  anonymous visitors through Sign in with ChatGPT.
- Use `chatGPTSignInPath(returnTo)` and `chatGPTSignOutPath(returnTo)` for
  browser links or actions.
- Pass a same-origin relative `returnTo` path for the destination after sign-in
  or sign-out. The helper validates and safely encodes it.
- Mark protected pages with `export const dynamic = "force-dynamic"` because
  they depend on per-request identity headers.

Dispatch owns `/signin-with-chatgpt`, `/signout-with-chatgpt`, `/callback`, the
OAuth cookies, and identity header injection. Do not implement app routes for
those reserved paths. Routes that do not import and call the helper remain
anonymous-compatible.

SIWC establishes identity only; it does not prove workspace membership. Use the
Sites hosting platform's access policy controls for workspace-wide restrictions,
or enforce explicit server-side membership or allowlist checks.

Use SIWC for account pages, user-specific dashboards, saved records, and write
actions tied to the current ChatGPT user. Leave public content anonymous.

## Diagnostic Commands

- `npm run install:ci`: perform the one bounded lockfile install
- `npm run dev`: start the Vite/Vinext development server
- `npm run build`: build and validate the deployable Sites artifact
- `npm run start`: start the built Vinext application
- `npm test`: build, validate, and verify the rendered development-preview metadata
- `npm run validate:artifact`: recheck an existing artifact's manifest and ESM `default.fetch` export
- `npm run db:generate`: generate Drizzle migrations after schema changes

Use build and validation commands for targeted diagnosis after a remote failure, not as part of the normal checkpoint path.

The timeout defaults can be overridden for a controlled canary with `SITES_INSTALL_TIMEOUT`, `SITES_INSTALL_KILL_AFTER`, `SITES_BUILD_TIMEOUT`, and `SITES_BUILD_KILL_AFTER`. A timeout fails the command; the helpers never retry an unchanged install or build.

## Learn More

- [vinext Documentation](https://github.com/cloudflare/vinext)
- [Drizzle D1 Guide](https://orm.drizzle.team/docs/get-started/d1-new)
