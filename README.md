# Portfolio Intelligence

Portfolio Intelligence is a read-only investment analysis workspace for Indian investors. It combines uploaded portfolio files, deterministic financial calculations, bounded AI research, and a conversational review experience.

The product was rebuilt from a clean repository baseline dated 26 August 2026. R0/R1 are locally
verified; R2/R3 now have an implementation checkpoint but are not production-approved.

## The important promise

This application does not promise that an investment will become 0.5x, 1.5x, or 2x. It helps a user understand what a goal requires, what risks exist, what changed, and which evidence should be reviewed before the human makes a decision.

It does not place orders. The AI cannot modify holdings, use protected cash, weaken portfolio rules, or connect to a broker’s trading endpoints.

## What works in the current milestone

| Area | Current status |
|---|---|
| Clean monorepo | Implemented |
| Responsive web workspace | Implemented |
| Portfolio creation and listing | Implemented |
| Native PDF, scanned-PDF detection, XLS, XLSX, and CSV intake | Implemented; supplied demo layouts normalize into typed evidence |
| File signature, size, active-content, and workbook safety checks | Implemented foundation |
| Upload status and metadata | Implemented |
| Deterministic goal CAGR and current-ledger analytics | Implemented |
| Versioned prices and supported corporate actions | Implemented API; licensed feed pending |
| Immutable valuation and risk snapshots | Implemented R2 checkpoint |
| TWR, MWR/XIRR, volatility, downside deviation, drawdown | Implemented; full qualification pending |
| Protected-reserve market-stress scenarios | Implemented; always non-executable |
| LangGraph portfolio-analysis workflow | Implemented bounded graph |
| AI provider connection | Configured through secrets; requires a key |
| PostgreSQL, Redis, and private quarantine object storage | Included in local Docker stack |
| Malware scanner | Implemented; optional local Docker profile, mandatory in production |
| Human-confirmed ledger publication | Implemented append-only API and certified-CSV workbench |
| Holdings, cash, P/L, and concentration monitors | Implemented deterministic foundation |
| TradingAgents research architecture | Adapted from pinned commit with analyst/debate/risk stages and categorical demo signal |
| Point-in-time evidence and numeric citations | Implemented R3 checkpoint; licensed connectors pending |
| Durable agent run provenance and checkpoints | Implemented; staging failover qualification pending |
| Production authentication and registered-adviser mode | Not enabled |
| Upstox read-only connection | Contract and secrets prepared; implementation pending |
| Trade execution | Intentionally absent |

The current build is an engineering and synthetic-data test candidate. It is not yet approved for
real-money decision-making: licensed data, AWS staging, R2/R3 evaluation, security, accessibility,
and regulatory gates remain open.

For the shortest file-to-chat showcase, follow the [TradingAgents demo runbook](docs/DEMO_MVP.md).

## Hosted Sites demo checkpoint

A responsive, owner-isolated Sites demo is active at [Portfolio Intelligence](https://portfolio-intelligence.satoshinara.chatgpt.site). The public repository now carries a sanitized, testable source snapshot under [`apps/sites-demo/`](apps/sites-demo/) and a [current status report](docs/SITES_DEMO_STATUS.md).

The snapshot keeps the data-to-agent-to-chat wiring, spreadsheet inference, consolidated-lot normalization, PDF metadata hashing, account-scoped analytics, responsive navigation, and deletion controls. It excludes owner portfolio data, source filenames and aggregates, customer-specific ticker aliases, runtime credentials, the live Sites project identifier, and generated build caches. The owner-only hosted deployment now uses the approved OpenRouter Gemma chat route and is connected to the authenticated external TradingAgents/LangGraph runtime; production-hardening gates remain.

## Who it is for

### Existing investors

An existing investor will:

1. Create a self-managed, PMS, model, or Portfolio of Interest portfolio.
2. Upload a brokerage XLS/XLSX/CSV file or a statement/research PDF.
3. Review detected file type, sheets/pages, and data-quality warnings.
4. Reconcile conflicts before any row becomes portfolio truth.
5. View deterministic holdings, return, benchmark, allocation, risk, and goal analytics.
6. Ask the AI what changed and inspect its evidence.
7. Compare scenarios and record a decision or no-action outcome.

### New investors

A new investor will:

1. Enter a goal, investment horizon, contribution plan, risk capacity, and protected reserve.
2. See the annual return the goal would require.
3. Receive an educational starting roadmap and allocation ranges.
4. Review downside and drawdown scenarios.
5. Save a plan without placing an order.

## Human control versus AI autonomy

| Activity | Human | Software/AI |
|---|---|---|
| Set goals, reserve, risk, and exclusions | Owns and confirms | Validates consistency |
| Publish data from a file | Must approve | Scans, parses, and flags conflicts |
| Calculate portfolio numbers | Reviews | Deterministic code is authoritative |
| Accept market/research evidence | Confirms source rights or delegates an approved provider | Enforces cutoff, hash, and schema |
| Research holdings | Selects scope and cutoff | Bounded agents compare allowlisted evidence |
| Consider a change | Makes the decision | Produces conditional scenarios |
| Place an investment order | Done outside this product | No execution capability |
| Improve AI behavior | Approves releases indirectly through product governance | Offline evaluation; no silent self-training |

## How the system works

~~~mermaid
flowchart TD
    U["User and web app"] --> A["Core portfolio API"]
    A --> D["Ledger and versioned analytics"]
    A --> F["Secure file intake"]
    U --> G["LangGraph agent service"]
    G --> A
    G --> C["Durable checkpoints"]
    A --> E["Point-in-time evidence"]
~~~

The core rule is simple: AI explains data; it does not create financial truth.

1. Files enter quarantine.
2. The API checks size, signature, type, and dangerous content.
3. A parser reads safe content without running macros, formulas, or PDF instructions.
4. Candidate rows wait for reconciliation and user approval.
5. Approved rows enter the append-only ledger; manual events require explicit publication confirmation.
6. An approved market-data version freezes prices, corporate actions, rights, and known-at time.
7. Deterministic code persists a valuation/risk snapshot tied to ledger, dataset, and methodology versions.
8. The adapted TradingAgents research panel receives typed metrics, evidence, rules, and a cutoff.
9. Policy and numeric-citation gates suppress unsupported or constraint-breaking output.
10. Core persists the public run stages, evidence links, output hash, and `can_execute: false` proposal.
11. The user receives an answer with evidence and remains the decision-maker.

## Quick start for a non-technical user

### What you need

- A computer with at least 8 GB RAM; 16 GB is recommended.
- Docker Desktop.
- Git.
- An OpenAI API key only if you want live-language synthesis; deterministic safe mode needs no key.
- About 10–15 minutes for first setup.

### Windows setup

1. Install Git for Windows.
2. Install Docker Desktop and enable its WSL 2 backend.
3. Restart the computer if Docker requests it.
4. Open PowerShell.
5. Clone the repository:

       git clone https://github.com/Bhargav2301/portfolio-intelligence.git
       cd portfolio-intelligence

6. Generate a local secrets file:

       python scripts/bootstrap_env.py

7. Open the new .env file in Notepad:

       notepad .env

8. Set OPENAI_API_KEY to your project key and OPENAI_MODEL to an approved model available in that project. Follow [the secrets guide](docs/SECRETS_SETUP.md).
9. Start the complete local stack:

       docker compose up --build

10. Wait until the terminal reports that the services are healthy.
11. Open:

    - Web application: http://localhost:3000
    - Core API documentation: http://localhost:8000/docs
    - Agent API documentation: http://localhost:8001/docs
    - Local object-storage console: http://localhost:9001

12. Stop the application with Ctrl+C. Start it again later with:

       docker compose up

Your .env file is excluded from Git. Never paste it into an issue, screenshot, chat, commit, or shared drive.

## Quick start for developers

### Full stack

    python scripts/bootstrap_env.py
    docker compose up --build

### Backend without Docker

    cd services/api
    python -m venv .venv
    .venv\Scripts\activate
    pip install -e ".[dev]"
    uvicorn portfolio_api.main:app --reload --port 8000

On macOS/Linux, activate with:

    source .venv/bin/activate

### Agent service without Docker

    cd services/agents
    python -m venv .venv
    source .venv/bin/activate
    pip install -e ".[dev]"
    uvicorn portfolio_agents.main:app --reload --port 8001

### Web application without Docker

    cd apps/web
    npm install
    npm run dev

### Tests and validation

    make test
    make check

## First API walkthrough

Development requests use a local workspace identifier. Production will replace this with verified OIDC membership.

Create a portfolio:

    curl -X POST http://localhost:8000/v1/portfolios \
      -H "Content-Type: application/json" \
      -H "X-Workspace-Id: 00000000-0000-0000-0000-000000000001" \
      -d "{\"name\":\"Core Equity\",\"portfolio_type\":\"self_managed\",\"base_currency\":\"INR\",\"benchmark_code\":\"NIFTY_500_TRI\",\"valuation_timezone\":\"Asia/Kolkata\"}"

List portfolios:

    curl http://localhost:8000/v1/portfolios \
      -H "X-Workspace-Id: 00000000-0000-0000-0000-000000000001"

Upload a file:

    curl -X POST http://localhost:8000/v1/uploads \
      -H "X-Workspace-Id: 00000000-0000-0000-0000-000000000001" \
      -F "portfolio_id=YOUR_PORTFOLIO_ID" \
      -F "source_role=brokerage_ledger" \
      -F "file=@YOUR_FILE.xlsx"

Ask the agent:

    curl -X POST http://localhost:8001/v1/agent-runs \
      -H "Content-Type: application/json" \
      -d "{\"portfolio_id\":\"YOUR_PORTFOLIO_ID\",\"question\":\"What should I review first?\"}"

## Secrets and API keys

Do not create a committed secrets file. The repository contains:

- [.env.example](.env.example): every supported setting with safe placeholders.
- [Secrets setup guide](docs/SECRETS_SETUP.md): where each credential comes from and how to test it.
- [Local environment generator](scripts/bootstrap_env.py): creates strong local-only secrets and writes .env.

The local setup generator also creates one shared internal secret used by the Agent API when it
records runs through Core. For production, OpenAI, market/news providers, Cognito, storage, database,
and internal-service values live in AWS Secrets Manager and KMS; none belong in source control.

## Portfolio protections

The initial workspace carries two explicit rules:

- Equal-weighting is not allowed.
- ₹25 lakh is protected reserve cash and cannot be allocated by a scenario.

These are versioned portfolio rules. An AI response cannot change them. A future human change must be explicit and auditable.

## Security model

- No credentials are sent to the browser.
- Uploaded files are quarantined before parsing.
- PDF instructions, spreadsheet formulas, macros, and external links are not executed.
- XLSM, XLSB, and ODS are rejected in the first milestone.
- Production configuration fails closed if malware scanning, authentication, or encryption is disabled.
- Every tenant-owned record carries a workspace identifier.
- PostgreSQL row-level security is enabled and forced on every tenant-owned R0–R3 table.
- Tenant-aware composite foreign keys reject cross-workspace parent identifiers.
- Historical analytics and evidence enforce both economic (`as_of`) and information (`known_at`) cutoffs.
- If terminal agent-run persistence or numeric-citation validation fails, the answer is withheld.
- Broker integration is read-only by design.
- No trade/order route or tool exists.

Report security issues privately using [SECURITY.md](SECURITY.md).

## Repository structure

    apps/web/                  Next.js web experience
    services/api/              Portfolio, file, ledger, and analytics API
    services/agents/           FastAPI and LangGraph agent runtime
    infra/postgres/            Database bootstrap and migrations
    docs/requirements/         Six approved foundation documents
    docs/SECRETS_SETUP.md      Credential setup
    docs/BUILD_PROGRESS.md     Implemented versus pending work
    scripts/                   Local setup and verification helpers

## Foundational documents

1. [Product Requirements Document](docs/requirements/01_Product_Requirements_Document.md)
2. [Market and Business Requirements](docs/requirements/02_Market_and_Business_Requirements_Document.md)
3. [Technical Design and System Architecture](docs/requirements/03_Technical_Design_and_System_Architecture.md)
4. [UX/UI Design Specification](docs/requirements/04_UX_UI_Design_Specification.md)
5. [Data Model and API Specification](docs/requirements/05_Data_Model_and_API_Specification.md)
6. [QA and Test Plan](docs/requirements/06_QA_and_Test_Plan.md)

Implementation must trace back to these documents. If code and a requirement conflict, update the decision record before changing behavior.

See [Unified architecture and delivery roadmap](docs/UNIFIED_ARCHITECTURE_AND_ROADMAP.md)
for the integration boundary, implemented endpoints, production topology, and remaining launch gates.
See the [R2/R3 implementation report](docs/production/R2_R3_IMPLEMENTATION_REPORT.md) for formulas,
data lineage, human/autonomous boundaries, API contracts, and the precise unfinished exit evidence.

## Delivery roadmap

### Milestone 1 — Foundation and safe intake

- Clean monorepo and local stack.
- Portfolio creation.
- Secure file identification and structural parsing.
- Initial dashboard.
- Bounded LangGraph workflow.
- Secrets and operations documentation.

### Milestone 2 — Reconciliation and portfolio truth

- Provider-specific file templates.
- Source/normalized row review workbench.
- Duplicate and conflict detection.
- Append-only transaction ledger.
- Holdings, cash, and historical snapshots.

### Milestone 3 — Analytics and evidence

- Implemented checkpoint: versioned valuation, TWR/MWR, volatility, downside deviation, drawdown,
  evidence records, numeric citations, and constrained scenarios.
- Pending: benchmark/active return, attribution, advanced corporate actions, market state, licensed
  provider workers, and full finance property qualification.

### Milestone 4 — Production agents and controls

- Implemented checkpoint: durable PostgreSQL checkpoints and Core run records, cutoff-safe context,
  risk/compliance gate, public stages, evidence, citations, and structural no-execution contracts.
- Pending: licensed research tools, interrupts/SSE/cancellation, ≥99% bounded-completion evaluation,
  canary qualification, and kill-switch exercise.
- Offline feedback and outcome evaluation.

### Milestone 5 — Beta hardening

- OIDC/MFA.
- Read-only Upstox.
- Accessibility, load, penetration, recovery, and compliance testing.
- Controlled beta and operating playbooks.

## Financial and regulatory notice

This repository is software under development. It does not provide guaranteed returns, execute trades, or replace a qualified professional. Personalized investment-adviser mode must remain disabled until the applicable legal, registration, suitability, recordkeeping, disclosure, and review model is approved.
