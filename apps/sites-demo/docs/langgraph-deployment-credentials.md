# Portfolio Intelligence LangGraph deployment and credential audit

Audit date: 2026-08-26  
Application: Portfolio Intelligence (PI) owner pilot  
TradingAgents baseline: `TauricResearch/TradingAgents` commit `a33fd4c0f134485a43553a2c23a63cb14adbd88f`

This report lists configuration names only. It intentionally contains no secret values.

## Executive finding

The PI web application is deployable on OpenAI Sites today, but the TradingAgents service is a separate Python deployment. The hosted Sites project currently has no runtime environment variables configured. As a result, the Upstox OAuth connector and server-to-server LangGraph bridge correctly remain disabled.

For the smallest working owner pilot, deploy the Python runtime with one supported LLM provider key and `PI_INTERNAL_API_TOKEN`, then configure the Sites worker with the runtime URL and the same bearer token. Upstox credentials are independent and are required only when read-only account linking is enabled.

## Deployment topology and exact prerequisites

### 1. PI web/dashboard

| Requirement | Exact value | Purpose |
|---|---|---|
| Runtime | Node.js `>=22.13.0` | Build and local development |
| Framework | Next.js `16.2.6`, React `19.2.6`, Vinext `0.0.50` | UI and server routes |
| Hosting | OpenAI Sites / Cloudflare Worker | Production web runtime |
| Database | Cloudflare D1 binding named `DB` | Owner-scoped portfolio ledger |
| Build host | Linux with Bash, `flock`, `curl`, and GNU `timeout` | Repository build scripts |
| Package install | `npm ci` from the committed lockfile | Reproducible dependencies |

The browser never receives LLM, broker, or service credentials. The Sites worker reads authenticated identity headers, owner-scopes every database query, and calls the Python service only from server routes.

### 2. LangGraph / TradingAgents runtime

| Requirement | Exact value | Purpose |
|---|---|---|
| Runtime | Python `>=3.10`; container uses Python `3.12-slim` | FastAPI and graph execution |
| System package | `git` | Installs the pinned TradingAgents Git dependency |
| HTTP service | FastAPI `>=0.115,<1`, Uvicorn `>=0.30,<1` | Private control plane |
| Graph engine | LangGraph `>=0.4.8,<1` | Required PI orchestration engine |
| Validation | Pydantic `>=2.9,<3` | Request/result contracts |
| Upstream | Pinned Git commit above | Reproducible agent behavior |
| Container identity | Non-root UID `10001` | Runtime hardening |
| Port | `8000` by default | Private service listener |

TradingAgents also installs LangChain provider packages, Pandas, yfinance, stockstats, Redis client support, and SQLite checkpoint support. Run one graph per process/container: TradingAgents configuration is process-global, so mixed provider configurations must not share a worker process. The current owner-pilot store is in memory and loses run history on restart. Production durability requires the Postgres/Redis work described below.

## Credential matrix

### Required for every deployed agent runtime

| Variable | Classification | Storage | Notes |
|---|---|---|---|
| `PI_INTERNAL_API_TOKEN` | Required secret | Agent runtime and Sites secret store | Long random bearer token shared only by the two server runtimes. Never expose it to browser code or logs. |
| One LLM provider credential from the next table | Required secret | Agent runtime secret store | Only the selected provider is required; do not configure every provider. |

`PI_ALLOW_INSECURE_LOCAL=true` disables bearer authentication for local development. It must never be set in production.

### LLM provider credentials — select one provider

| Provider | Required variables | Additional configuration |
|---|---|---|
| OpenAI | `OPENAI_API_KEY` | Set provider/model configuration described below. |
| Anthropic | `ANTHROPIC_API_KEY` | None beyond model selection. |
| Google Gemini | `GOOGLE_API_KEY` | None beyond model selection. |
| Azure OpenAI | `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_DEPLOYMENT_NAME`, `OPENAI_API_VERSION` | All four are required for the Azure client. |
| xAI | `XAI_API_KEY` | None beyond model selection. |
| DeepSeek | `DEEPSEEK_API_KEY` | None beyond model selection. |
| Qwen international | `DASHSCOPE_API_KEY` | Use the international provider option. |
| Qwen China | `DASHSCOPE_CN_API_KEY` | Use the China provider option. |
| GLM international | `ZHIPU_API_KEY` | Use the international provider option. |
| GLM China | `ZHIPU_CN_API_KEY` | Use the China provider option. |
| MiniMax global | `MINIMAX_API_KEY` | Use the global provider option. |
| MiniMax China | `MINIMAX_CN_API_KEY` | Use the China provider option. |
| OpenRouter | `OPENROUTER_API_KEY` | None beyond model selection. |
| Mistral | `MISTRAL_API_KEY` | None beyond model selection. |
| Moonshot / Kimi | `MOONSHOT_API_KEY` | None beyond model selection. |
| Groq | `GROQ_API_KEY` | None beyond model selection. |
| NVIDIA | `NVIDIA_API_KEY` | None beyond model selection. |
| OpenAI-compatible endpoint | `OPENAI_COMPATIBLE_API_KEY` when the endpoint requires it | Also set the backend URL. |
| Ollama | No credential | `OLLAMA_BASE_URL` is optional; the service must be reachable from the runtime. |
| AWS Bedrock | AWS credential chain: workload/IAM role, or `AWS_ACCESS_KEY_ID` plus `AWS_SECRET_ACCESS_KEY`; `AWS_SESSION_TOKEN` when temporary; alternatively `AWS_BEARER_TOKEN_BEDROCK` | Set `AWS_REGION` or `AWS_DEFAULT_REGION`; install the `bedrock` dependency extra. Prefer workload identity over long-lived access keys. |

### TradingAgents and PI graph configuration

These are configuration values, not credentials.

| Variable | Default / requirement | Meaning |
|---|---|---|
| `TA_LLM_PROVIDER` | Uses upstream default if omitted | PI adapter provider selector |
| `TA_DEEP_THINK_LLM` | Uses upstream default if omitted | Debate/research model |
| `TA_QUICK_THINK_LLM` | Uses upstream default if omitted | Analyst/tool model |
| `TA_BACKEND_URL` | Provider default | Custom provider endpoint |
| `TA_MAX_DEBATE_ROUNDS` | `1` | Bounded research debate |
| `TA_MAX_RISK_ROUNDS` | `1` | Bounded risk debate |
| `TA_ONLINE_TOOLS` | `true` | Enables external data tools |
| `TA_CONFIG_JSON` | Empty | Advanced JSON overrides; treat as sensitive configuration even if it should not contain keys |
| `TRADINGAGENTS_RESULTS_DIR` | `/tmp/pi-tradingagents` in PI runtime | Run artifacts |
| `TRADINGAGENTS_CACHE_DIR` | Upstream user-data directory | Tool cache and optional SQLite checkpoints |
| `TRADINGAGENTS_MEMORY_LOG_PATH` | Upstream user-data directory | Agent memory log path |

Upstream also recognizes `TRADINGAGENTS_LLM_PROVIDER`, `TRADINGAGENTS_DEEP_THINK_LLM`, `TRADINGAGENTS_QUICK_THINK_LLM`, `TRADINGAGENTS_LLM_BACKEND_URL`, `TRADINGAGENTS_OUTPUT_LANGUAGE`, `TRADINGAGENTS_MAX_DEBATE_ROUNDS`, `TRADINGAGENTS_MAX_RISK_ROUNDS`, `TRADINGAGENTS_CHECKPOINT_ENABLED`, `TRADINGAGENTS_BENCHMARK_TICKER`, `TRADINGAGENTS_TEMPERATURE`, `TRADINGAGENTS_LLM_MAX_RETRIES`, and provider-specific reasoning-effort settings. PI's `TA_*` variables are applied after loading upstream defaults. Do not set both namespaces for the same option unless their values are identical; conflicting duplicate configuration is operationally ambiguous.

### Market-data credentials

| Variable | When required | Notes |
|---|---|---|
| `FRED_API_KEY` | Required when the macro/FRED tool is enabled | Store only in the agent runtime. |
| `ALPHA_VANTAGE_API_KEY` | Required only when Alpha Vantage is selected | The default yfinance path is keyless. |

yfinance, Reddit RSS, StockTwits public endpoints, and the default Polymarket path are keyless but still require outbound HTTPS, DNS, rate-limit handling, and explicit egress policy. Market identifiers must be confirmed (`.NS` for NSE or `.BO` for BSE) before a run.

### Sites and broker-link credentials

| Variable | Classification | Required when |
|---|---|---|
| `TRADING_AGENTS_API_URL` | Sensitive configuration | The web UI is connected to the private agent runtime. |
| `TRADING_AGENTS_API_TOKEN` | Required secret | Must equal the runtime's `PI_INTERNAL_API_TOKEN`. |
| `UPSTOX_CLIENT_ID` | Sensitive credential | Upstox OAuth is enabled. |
| `UPSTOX_CLIENT_SECRET` | Required secret | Upstox OAuth is enabled. |
| `UPSTOX_REDIRECT_URI` | Configuration | Must exactly match the registered production callback. |
| `CONNECTOR_ENCRYPTION_KEY` | Required secret | Encrypts broker access tokens with AES-GCM; use a high-entropy value and maintain a rotation plan. |

The current Upstox integration reads holdings only. PI does not collect a brokerage password and does not expose an order endpoint.

### LangGraph state and production infrastructure

Local LangGraph execution requires no LangGraph API key. In the current V1, the PI run store is in-memory and upstream checkpointing is disabled unless explicitly enabled. If `TRADINGAGENTS_CHECKPOINT_ENABLED=true`, the runtime needs a writable, persistent `TRADINGAGENTS_CACHE_DIR`; this is local SQLite state, not a hosted service token.

The following are production requirements in the approved architecture but are **not yet consumed by the V1 runtime code**:

| Future variable | Classification | Purpose |
|---|---|---|
| `DATABASE_URL` or `PI_DATABASE_URL` | Required production secret | Postgres run records, idempotency, audit linkage, and restart-safe status. Standardize on one name during the durable-store implementation. |
| `REDIS_URL` | Required production secret | Queue/stream transport, worker fan-out, event delivery, and cancellation. |

LangSmith is not referenced by the current code. `LANGSMITH_API_KEY` and `LANGSMITH_PROJECT` are therefore not required. Add them only with a separate tracing decision, privacy review, and prompt/portfolio redaction policy.

## Network and storage requirements

- Sites must reach the private agent API over HTTPS; the API must reject requests without the bearer token and should use an ingress allowlist or private gateway.
- The agent runtime needs outbound HTTPS to the chosen LLM provider and enabled market-data vendors.
- Persist `TRADINGAGENTS_RESULTS_DIR`, `TRADINGAGENTS_CACHE_DIR`, and `TRADINGAGENTS_MEMORY_LOG_PATH` if artifacts/checkpoints must survive restarts. Encrypt persistent volumes and apply retention limits.
- A durable production topology needs managed Postgres and Redis with TLS, backups, point-in-time recovery where available, and least-privilege service accounts.
- Supplied PDFs contain personal and account information. Do not place raw documents in D1 or source control. Use private object storage with per-owner authorization before enabling uploads; D1 should retain only hashes, metadata, and normalized records.

## Secret generation, storage, and rotation

1. Generate `PI_INTERNAL_API_TOKEN` and `CONNECTOR_ENCRYPTION_KEY` with a cryptographically secure random generator; use at least 32 random bytes.
2. Store Sites-side values in the Sites production secret store, never `.openai/hosting.json` or a committed `.env` file.
3. Store runtime secrets in the deployment platform's managed secret store and inject them at process start.
4. Scope provider credentials to the smallest available project, budget, and permission set. Configure spend/rate alerts.
5. Rotate the internal bearer token with a short dual-key overlap. Rotating `CONNECTOR_ENCRYPTION_KEY` requires decrypt-and-re-encrypt migration or forced broker reconnection.
6. Redact authorization headers, provider payloads, prompts, portfolio quantities, and broker tokens from logs and telemetry.

## Deployment verification sequence

1. Build the Sites application with `npm ci`, `npm run lint`, and `npm test`.
2. Build the runtime image from `services/agent-runtime/Dockerfile`; run its tests and start exactly one Uvicorn worker.
3. Confirm unauthenticated runtime requests return `401` and authenticated `/health` succeeds.
4. Configure one LLM provider and run a single confirmed test ticker with a strict timeout and cost cap.
5. Configure Sites `TRADING_AGENTS_API_URL` and secret `TRADING_AGENTS_API_TOKEN`; redeploy the saved Sites version.
6. Confirm the Agent desk reports the runtime version and graph engine `langgraph` before accepting a run.
7. Configure broker credentials separately, then verify OAuth state expiry, encrypted token storage, holdings-only sync, and last-sync telemetry.
8. Do not enable multi-user use until Postgres/Redis durability, tenant-isolation tests, and backup/restore checks pass.

## Audit conclusion

The source contains no embedded credential values. The production Sites environment is currently empty, so agent execution and broker OAuth are not active. The minimum missing inputs are a deployed runtime URL, one shared internal bearer token, and one selected LLM provider credential. Durable LangGraph state is an implementation gap rather than a missing current secret; Postgres and Redis must be added before production or multi-user rollout.
