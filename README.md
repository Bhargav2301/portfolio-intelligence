# Portfolio Intelligence

Portfolio Intelligence is a read-only investment analysis workspace for Indian investors. It combines uploaded portfolio files, deterministic financial calculations, bounded AI research, and a conversational review experience.

The product is being rebuilt from a clean repository baseline dated 26 August 2026.

## The important promise

This application does not promise that an investment will become 0.5x, 1.5x, or 2x. It helps a user understand what a goal requires, what risks exist, what changed, and which evidence should be reviewed before the human makes a decision.

It does not place orders. The AI cannot modify holdings, use protected cash, weaken portfolio rules, or connect to a broker’s trading endpoints.

## What works in the current milestone

| Area | Current status |
|---|---|
| Clean monorepo | Implemented |
| Responsive web workspace | Implemented |
| Portfolio creation and listing | Implemented |
| Native PDF, scanned-PDF detection, XLS, XLSX, and CSV intake | Implemented foundation |
| File signature, size, active-content, and workbook safety checks | Implemented foundation |
| Upload status and metadata | Implemented |
| Deterministic goal CAGR and empty-portfolio analytics | Implemented |
| LangGraph portfolio-analysis workflow | Implemented foundation |
| AI provider connection | Configured through secrets; requires a key |
| PostgreSQL, Redis, and private quarantine object storage | Included in local Docker stack |
| Malware scanner | Implemented; optional local Docker profile, mandatory in production |
| Full transaction reconciliation and publication | Next milestone |
| Production authentication and registered-adviser mode | Not enabled |
| Upstox read-only connection | Contract and secrets prepared; implementation pending |
| Trade execution | Intentionally absent |

The current build is an engineering foundation and first vertical slice. It is not yet suitable for real-money decision-making.

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
| Research holdings | Selects scope | Bounded agents collect and compare evidence |
| Consider a change | Makes the decision | Produces conditional scenarios |
| Place an investment order | Done outside this product | No execution capability |
| Improve AI behavior | Approves releases indirectly through product governance | Offline evaluation; no silent self-training |

## How the system works

~~~mermaid
flowchart TD
    U["User and web app"] --> A["Core portfolio API"]
    A --> D["PostgreSQL ledger and analytics"]
    A --> F["Secure file intake"]
    U --> G["LangGraph agent service"]
    G --> A
    G --> M["Approved model and data providers"]
~~~

The core rule is simple: AI explains data; it does not create financial truth.

1. Files enter quarantine.
2. The API checks size, signature, type, and dangerous content.
3. A parser reads safe content without running macros, formulas, or PDF instructions.
4. Candidate rows wait for reconciliation and user approval.
5. Approved rows enter the append-only ledger.
6. Deterministic code calculates portfolio metrics.
7. LangGraph agents receive typed metrics, evidence, rules, and an as-of timestamp.
8. A policy gate blocks unsupported or constraint-breaking output.
9. The user receives an answer with evidence and remains the decision-maker.

## Quick start for a non-technical user

### What you need

- A computer with at least 8 GB RAM; 16 GB is recommended.
- Docker Desktop.
- Git.
- An OpenAI API key for live AI answers.
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

The only external credential required for the first live AI milestone is OPENAI_API_KEY. Database, Redis, object-storage, encryption, authentication, market-data, LangSmith, email, and Upstox settings are documented separately and are enabled only when the related feature is used.

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
- PostgreSQL row-level-security migration is included.
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

- TWR/MWR, benchmark, attribution, concentration, volatility, and drawdown.
- Market-state snapshots.
- Research evidence repository and citations.
- Scenario engine with reserve and allocation constraints.

### Milestone 4 — Production agents and controls

- Durable PostgreSQL checkpoints.
- Point-in-time research tools.
- Risk/compliance gate.
- User-visible agent telemetry.
- Offline feedback and outcome evaluation.

### Milestone 5 — Beta hardening

- OIDC/MFA.
- Read-only Upstox.
- Accessibility, load, penetration, recovery, and compliance testing.
- Controlled beta and operating playbooks.

## Financial and regulatory notice

This repository is software under development. It does not provide guaranteed returns, execute trades, or replace a qualified professional. Personalized investment-adviser mode must remain disabled until the applicable legal, registration, suitability, recordkeeping, disclosure, and review model is approved.
