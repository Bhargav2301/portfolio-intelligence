[CmdletBinding()]
param(
    [switch]$PromptForOpenRouterKey,
    [string]$TradingAgentsApiUrl = ""
)

$ErrorActionPreference = "Stop"

$repositoryRoot = Split-Path -Parent $PSScriptRoot
$sitesEnvironmentPath = Join-Path $repositoryRoot "apps/sites-demo/.env.local"
$runtimeEnvironmentPath = Join-Path $repositoryRoot "apps/sites-demo/services/agent-runtime/.env.runtime.local"

function Read-EnvironmentValue {
    param(
        [string]$Path,
        [string]$Name
    )

    if (-not (Test-Path -LiteralPath $Path)) {
        return ""
    }

    $prefix = "$Name="
    $line = Get-Content -LiteralPath $Path |
        Where-Object { $_.StartsWith($prefix, [StringComparison]::Ordinal) } |
        Select-Object -First 1

    if ($null -eq $line) {
        return ""
    }

    return $line.Substring($prefix.Length)
}

function New-HexSecret {
    $bytes = New-Object byte[] 32
    [System.Security.Cryptography.RandomNumberGenerator]::Fill($bytes)
    return ([BitConverter]::ToString($bytes)).Replace("-", "").ToLowerInvariant()
}

function ConvertFrom-SecureValue {
    param([Security.SecureString]$SecureValue)

    $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($SecureValue)
    try {
        return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
    }
    finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer)
    }
}

function Assert-SingleLineValue {
    param(
        [string]$Name,
        [string]$Value
    )

    if ($Value -match "[`r`n]") {
        throw "$Name must be a single-line value."
    }
}

$sitesToken = Read-EnvironmentValue -Path $sitesEnvironmentPath -Name "TRADING_AGENTS_API_TOKEN"
$runtimeToken = Read-EnvironmentValue -Path $runtimeEnvironmentPath -Name "PI_INTERNAL_API_TOKEN"

if ($sitesToken -and $runtimeToken -and $sitesToken -cne $runtimeToken) {
    throw "Existing Sites and runtime tokens do not match. Resolve them before continuing."
}

$internalToken = if ($sitesToken) {
    $sitesToken
}
elseif ($runtimeToken) {
    $runtimeToken
}
else {
    New-HexSecret
}

$openRouterKey = Read-EnvironmentValue -Path $sitesEnvironmentPath -Name "PORTFOLIO_LLM_API_KEY"
if (-not $openRouterKey) {
    $openRouterKey = Read-EnvironmentValue -Path $runtimeEnvironmentPath -Name "OPENROUTER_API_KEY"
}

if ($PromptForOpenRouterKey) {
    $secureKey = Read-Host "OpenRouter API key" -AsSecureString
    $openRouterKey = ConvertFrom-SecureValue -SecureValue $secureKey
    if (-not $openRouterKey) {
        throw "The OpenRouter API key cannot be empty."
    }
}

if (-not $TradingAgentsApiUrl) {
    $TradingAgentsApiUrl = Read-EnvironmentValue -Path $sitesEnvironmentPath -Name "TRADING_AGENTS_API_URL"
}

Assert-SingleLineValue -Name "OpenRouter API key" -Value $openRouterKey
Assert-SingleLineValue -Name "TradingAgents API URL" -Value $TradingAgentsApiUrl

$sitesLines = @(
    "PORTFOLIO_LLM_API_URL=https://openrouter.ai/api/v1/chat/completions"
    "PORTFOLIO_LLM_API_KEY=$openRouterKey"
    "PORTFOLIO_LLM_MODEL=google/gemma-4-26b-a4b-it"
    "PORTFOLIO_LLM_PROVIDER=OpenRouter Gemma 4"
    "TRADING_AGENTS_API_URL=$TradingAgentsApiUrl"
    "TRADING_AGENTS_API_TOKEN=$internalToken"
)

$runtimeLines = @(
    "PORT=8000"
    "OPENROUTER_API_KEY=$openRouterKey"
    "PI_INTERNAL_API_TOKEN=$internalToken"
    "TA_LLM_PROVIDER=openrouter"
    "TA_QUICK_THINK_LLM=google/gemma-4-26b-a4b-it"
    "TA_DEEP_THINK_LLM=z-ai/glm-5.3-flash"
    "TA_MAX_DEBATE_ROUNDS=1"
    "TA_MAX_RISK_ROUNDS=1"
    "TA_ONLINE_TOOLS=true"
    "TRADINGAGENTS_RESULTS_DIR=/tmp/pi-tradingagents"
)

[IO.Directory]::CreateDirectory((Split-Path -Parent $sitesEnvironmentPath)) | Out-Null
[IO.Directory]::CreateDirectory((Split-Path -Parent $runtimeEnvironmentPath)) | Out-Null
[IO.File]::WriteAllLines($sitesEnvironmentPath, $sitesLines, [Text.UTF8Encoding]::new($false))
[IO.File]::WriteAllLines($runtimeEnvironmentPath, $runtimeLines, [Text.UTF8Encoding]::new($false))

Write-Output "Sites environment prepared: $sitesEnvironmentPath"
Write-Output "Runtime environment prepared: $runtimeEnvironmentPath"
Write-Output "The internal token was synchronized without printing its value."
if ($openRouterKey) {
    Write-Output "The OpenRouter key is configured locally."
}
else {
    Write-Output "The OpenRouter key is still blank; rerun with -PromptForOpenRouterKey."
}
