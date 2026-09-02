# Render and TradingAgents activation guide

Last verified: 2 September 2026

This guide activates the external Portfolio Intelligence TradingAgents runtime on
Render and connects it to the owner-only OpenAI Sites deployment. It contains no
secret values. The runtime remains research-only and cannot place trades.

## Current approved model configuration

| Role | OpenRouter model |
|---|---|
| Portfolio chat | `google/gemma-4-26b-a4b-it` |
| TradingAgents quick thinking | `google/gemma-4-26b-a4b-it` |
| TradingAgents deep thinking | `z-ai/glm-5.3-flash` |

Both selected routes are billed OpenRouter routes. Keep a project budget and usage
alerts enabled. The free Gemma route returned provider `429` responses during the
31 August 2026 preflight. The retired `stealth/ox-alpha` identifier must not be used.

## Before you begin

You need:

1. Access to the GitHub repository `Bhargav2301/portfolio-intelligence`.
2. A Render account that can connect to that repository.
3. The OpenRouter API key already saved in the local ignored environment files.
4. The generated internal token already saved locally and in the Sites secret store.
5. A Render plan suitable for a continuously available demo. A sleeping instance can
   make Agent Desk health checks fail during cold starts.

The repository root used in the commands below is:

```text
C:\Projects\super_portfolio_inteligence\portfolio-intelligence
```

Do not paste either secret into chat, GitHub, source files, build commands, or any
variable whose name begins with `NEXT_PUBLIC_`.

## Step 3: Deploy the TradingAgents runtime on Render

### 3.1 Create the Render web service

1. Sign in to the [Render Dashboard](https://dashboard.render.com/).
2. Select **New**, then **Web Service**.
3. Connect GitHub if it is not already connected.
4. Select `Bhargav2301/portfolio-intelligence`.
5. Configure the service with these values:

| Render field | Value |
|---|---|
| Name | `portfolio-intelligence-agent-runtime` |
| Region | The region closest to the owner and the Sites deployment |
| Branch | `main` |
| Root Directory | `apps/sites-demo/services/agent-runtime` |
| Runtime | `Docker` |
| Dockerfile Path | `./Dockerfile` |
| Docker Build Context Directory | `.` |
| Health Check Path | `/health` |
| Auto-Deploy | `On Commit` after the first controlled deployment succeeds |

Do not override the Docker command. The committed Dockerfile starts Uvicorn on
`0.0.0.0`, reads `PORT`, and fixes the worker count at one.

### 3.2 Add the two protected secrets

In the Render service form, open **Advanced** and add these environment variables.
Treat both values as secrets:

| Key | Value |
|---|---|
| `OPENROUTER_API_KEY` | The existing OpenRouter API key |
| `PI_INTERNAL_API_TOKEN` | The generated internal token |

To copy the OpenRouter key from the ignored local file without printing it, run:

```powershell
Set-Location 'C:\Projects\super_portfolio_inteligence\portfolio-intelligence'
$line = Get-Content -LiteralPath 'apps/sites-demo/services/agent-runtime/.env.runtime.local' |
  Where-Object { $_ -like 'OPENROUTER_API_KEY=*' } |
  Select-Object -First 1
Set-Clipboard -Value $line.Substring('OPENROUTER_API_KEY='.Length)
Remove-Variable line
```

Paste the clipboard value into Render, then clear the clipboard:

```powershell
Set-Clipboard -Value ''
```

Repeat for the internal token:

```powershell
$line = Get-Content -LiteralPath 'apps/sites-demo/services/agent-runtime/.env.runtime.local' |
  Where-Object { $_ -like 'PI_INTERNAL_API_TOKEN=*' } |
  Select-Object -First 1
Set-Clipboard -Value $line.Substring('PI_INTERNAL_API_TOKEN='.Length)
Remove-Variable line
```

After pasting it into Render, clear the clipboard again.

### 3.3 Add the non-secret runtime configuration

Add these normal server-side environment variables:

```dotenv
PORT=8000
TA_LLM_PROVIDER=openrouter
TA_QUICK_THINK_LLM=google/gemma-4-26b-a4b-it
TA_DEEP_THINK_LLM=z-ai/glm-5.3-flash
TA_MAX_DEBATE_ROUNDS=1
TA_MAX_RISK_ROUNDS=1
TA_ONLINE_TOOLS=true
TRADINGAGENTS_RESULTS_DIR=/tmp/pi-tradingagents
```

Do not add `TA_BACKEND_URL`; the pinned TradingAgents code already knows the
OpenRouter endpoint. Do not add `PI_ALLOW_INSECURE_LOCAL=true`; it disables bearer
authentication and is never acceptable on Render.

### 3.4 Create and observe the first deployment

1. Select the Render plan. A paid always-on instance is preferable for a live demo;
   a free instance can cold-start or sleep.
2. Select **Create Web Service**.
3. Watch the build log until dependency installation and the Docker build complete.
4. Confirm the service starts one Uvicorn worker.
5. Confirm Render reports the `/health` check as passing.
6. If the build fails while installing TradingAgents, verify that the service uses
   the repository's Dockerfile and that outbound GitHub access is available.

Render supplies an HTTPS URL similar to:

```text
https://portfolio-intelligence-agent-runtime.onrender.com
```

Keep only the base URL. Do not append `/health` or `/v1/runs` when configuring Sites.

## Step 4: Test the OpenRouter models

The 31 August 2026 preflight already proved that the stored key can call both approved
models. To repeat the check without writing or printing the key, start PowerShell in
the repository root and run:

```powershell
$line = Get-Content -LiteralPath 'apps/sites-demo/services/agent-runtime/.env.runtime.local' |
  Where-Object { $_ -like 'OPENROUTER_API_KEY=*' } |
  Select-Object -First 1
$env:OPENROUTER_API_KEY = $line.Substring('OPENROUTER_API_KEY='.Length)
Remove-Variable line

function Test-OpenRouterModel([string]$Model) {
  $headers = @{ Authorization = "Bearer $env:OPENROUTER_API_KEY" }
  $body = @{
    model = $Model
    messages = @(@{ role = 'user'; content = 'Reply with MODEL_OK only.' })
    max_tokens = 512
    temperature = 0
    reasoning = @{ effort = 'low'; exclude = $true }
  } | ConvertTo-Json -Depth 7

  $result = Invoke-RestMethod `
    -Uri 'https://openrouter.ai/api/v1/chat/completions' `
    -Method Post `
    -Headers $headers `
    -ContentType 'application/json' `
    -Body $body

  $result.choices[0].message.content
}

Test-OpenRouterModel 'google/gemma-4-26b-a4b-it'
Test-OpenRouterModel 'z-ai/glm-5.3-flash'
Remove-Item Env:OPENROUTER_API_KEY
```

Both calls should return `MODEL_OK`. Do not use `stealth/ox-alpha`; OpenRouter has
retired that testing identifier in favor of `z-ai/glm-5.3-flash`.

## Step 5: Verify the Render deployment

Replace the example URL below with the Render base URL:

```powershell
$runtimeUrl = 'https://portfolio-intelligence-agent-runtime.onrender.com'
Invoke-RestMethod -Uri "$runtimeUrl/health"
```

Expected fields include:

```json
{
  "status": "ok",
  "runtime": "tradingagents",
  "orchestration": "langgraph",
  "workflow": "pi-portfolio-v1",
  "version": "0.3.0"
}
```

The health route is intentionally public and contains no portfolio data. Confirm that
a protected route rejects a request without the internal bearer token:

```powershell
try {
  Invoke-WebRequest -Uri "$runtimeUrl/v1/runs/not-a-real-run" -ErrorAction Stop
  throw 'Expected an authentication failure.'
}
catch {
  if ($_.Exception.Response.StatusCode.value__ -ne 401) { throw }
  'AUTH_GUARD_OK'
}
```

If `/health` fails, check Render's deploy log, the `PORT` setting, and the health-check
path. Do not continue until HTTPS health succeeds.

## Step 6: Activate standard Gemma in Portfolio Intelligence chat

The owner Site's pending environment revision is configured with:

```dotenv
PORTFOLIO_LLM_API_URL=https://openrouter.ai/api/v1/chat/completions
PORTFOLIO_LLM_MODEL=google/gemma-4-26b-a4b-it
PORTFOLIO_LLM_PROVIDER=OpenRouter Gemma 4
```

`PORTFOLIO_LLM_API_KEY` is stored as a protected Sites secret. The URL must include
`/chat/completions`. Saved Site version 18 was privately redeployed with environment
revision 6 on 2 September 2026 after the protected chat credential was revalidated.
Redeploy the saved version again whenever a later Sites
environment revision changes these values.

## Step 7: Connect Sites to the Render runtime

This connection was completed on 2 September 2026. Sites environment revision 6
contains the verified Render base URL and the protected matching token, and saved Site
version 18 was privately redeployed. For a replacement runtime or token rotation, set
these two Sites production variables:

```dotenv
TRADING_AGENTS_API_URL=https://YOUR-SERVICE.onrender.com
TRADING_AGENTS_API_TOKEN=<same value as Render PI_INTERNAL_API_TOKEN>
```

Provide the replacement URL to the project operator without any token or API key. The
operator must save the environment revision and privately redeploy the saved Site
version so the updated runtime configuration becomes active.

Do not add a trailing endpoint path. A trailing slash is tolerated, but the bare base
URL is preferred.

## Step 8: Validate Portfolio Intelligence end to end

Use synthetic portfolio data for this first run.

1. Open the owner-only Portfolio Intelligence Site.
2. Open **Settings** and confirm the LLM status shows `OpenRouter Gemma 4` and
   `google/gemma-4-26b-a4b-it`.
3. Ask chat to summarize the current synthetic holdings and largest concentration.
4. Confirm the response identifies the live model rather than the deterministic
   fallback.
5. Open **Agent Desk**.
6. Confirm it reports an external `tradingagents` runtime, version `0.3.0`, and a
   successful health check.
7. Select one confirmed NSE or BSE holding and the smallest analyst configuration.
8. Start one run and monitor its events until it reaches a terminal state.
9. Confirm Gemma is the quick-thinking model and GLM-5.3-Flash is the deep-thinking
   model in the Render logs without logging prompts, portfolio values, or headers.
10. Confirm the result remains advisory research and that no order or brokerage
    execution control exists.

## Troubleshooting

| Symptom | Check |
|---|---|
| Render deploy cannot find the Dockerfile | Root Directory must be `apps/sites-demo/services/agent-runtime`; Dockerfile Path is `./Dockerfile`. |
| Render reports no open port | Set `PORT=8000`; keep the committed Docker command unchanged. |
| `/health` times out | Check instance cold start, deploy logs, plan availability, and Render health status. |
| Runtime returns `401` | `TRADING_AGENTS_API_TOKEN` in Sites must exactly match `PI_INTERNAL_API_TOKEN` in Render. |
| Chat uses deterministic fallback | Confirm all four `PORTFOLIO_LLM_*` values exist and redeploy the saved Site version. |
| OpenRouter returns `401` | Rotate or recopy the provider key in both Render and Sites. |
| OpenRouter returns `429` | Check account limits and provider capacity; the approved standard Gemma route is not the free alias. |
| Model not found | Use `google/gemma-4-26b-a4b-it` and `z-ai/glm-5.3-flash` exactly. |
| One small-cap symbol lacks provider coverage | Version `0.3.0` records an explicit `Unknown` abstention for that symbol and continues the portfolio run. Review the fallback event and source coverage. |
| Agent Desk remains demo-safe | Configure the Render base URL in Sites and redeploy. |
| Health passes but a run fails | Inspect sanitized Render logs for provider, ticker mapping, outbound-data, or tool-call failures. |

## Security and operating limits

- Keep the Site owner-only during this activation.
- Use synthetic holdings for the first model and agent validation.
- Never log authorization headers, provider keys, internal tokens, prompts, raw
  documents, quantities, or acquisition costs.
- Keep OpenRouter budget limits and alerts enabled.
- Render's current runtime store is in memory; run history is lost on restart.
- Do not enable multi-user or public production traffic until durable Postgres/Redis
  state, tenant isolation, retention, backup/restore, and privacy gates are complete.
- Rotate demo keys after the activation exercise if they were exposed outside the
  intended secret stores.

## Official references

- [Render web services](https://render.com/docs/web-services)
- [Render monorepo support](https://render.com/docs/monorepo-support)
- [Render environment variables and secrets](https://render.com/docs/configure-environment-variables)
- [Render health checks](https://render.com/docs/health-checks)
- [OpenRouter Gemma 4 26B A4B](https://openrouter.ai/google/gemma-4-26b-a4b-it)
- [OpenRouter GLM-5.3-Flash](https://openrouter.ai/z-ai/glm-5.3-flash)
- [OpenRouter Ox Alpha disclosure](https://openrouter.ai/stealth/ox-alpha)
