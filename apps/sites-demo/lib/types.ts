export type Position = {
  symbol: string;
  name: string;
  exchange: string;
  analysisSymbol: string | null;
  mappingStatus: "confirmed" | "unresolved" | "unavailable";
  quantity: number;
  averageCost: number;
  currentPrice: number;
  marketValue: number;
  costBasis: number;
  unrealizedGain: number;
  returnPercent: number;
  allocationPercent: number;
  priceSource: string;
  priceAsOf: string;
};

export type LedgerTransaction = {
  id: string;
  symbol: string;
  name: string;
  type: "buy" | "sell" | "reversal";
  quantity: number;
  unitPrice: number;
  fees: number;
  occurredAt: string;
  reversesTransactionId: string | null;
  reversed: boolean;
};

export type Evidence = {
  id: string;
  symbol: string;
  title: string;
  publisher: string;
  sourceTier: number;
  sourceUri: string;
  publishedAt: string;
  summary: string;
  status: "verified" | "stale" | "conflicting";
};

export type EvidenceDocument = {
  id: string;
  symbol: string | null;
  filename: string;
  title: string;
  publisher: string | null;
  publishedAt: string | null;
  sourceHash: string;
  status: "metadata_only" | "uploaded" | "parsed" | "reviewed" | "rejected";
};

export type DashboardData = {
  status: "ready";
  portfolio: {
    id: string;
    name: string;
    baseCurrency: string;
    isDemo: boolean;
  };
  metrics: {
    totalValue: number;
    totalCost: number;
    totalGain: number;
    returnPercent: number;
    dayChange: number;
    dayChangePercent: number;
    evidenceCoverage: number;
  };
  positions: Position[];
  transactions: LedgerTransaction[];
  evidence: Evidence[];
  documents: EvidenceDocument[];
  valueHistory: Array<{ label: string; value: number }>;
  benchmarkHistory: Array<{
    id: "nifty50" | "sensex";
    label: string;
    sourceLabel: string;
    sourceUri: string;
    points: Array<{ label: string; value: number }>;
  }>;
  asOf: string;
  sourceMode: "manual" | "connected" | "demo";
  connections: BrokerConnection[];
  agentPolicy: AgentPolicy;
};

export type BrokerConnection = {
  provider: "upstox" | "zerodha";
  label: string;
  configured: boolean;
  status: "not_connected" | "connected" | "expired" | "action_required";
  readOnly: true;
  lastSyncedAt: string | null;
  expiresAt: string | null;
  detail: string;
};

export type SetupData = {
  status: "needs_setup";
  connections: BrokerConnection[];
  supportedCurrencies: ["INR"];
  csvColumns: ["symbol", "name", "exchange", "quantity", "average_cost", "current_price"];
};

export type PortfolioResponse = DashboardData | SetupData;

export type HoldingInput = {
  symbol: string;
  name: string;
  exchange: string;
  quantity: number;
  averageCost: number;
  currentPrice: number;
  analysisSymbol?: string | null;
};

export type PortfolioImportSource = {
  kind: "manual" | "csv" | "xls" | "normalized_json";
  filename: string | null;
  sha256: string;
};

export type HoldingLotInput = {
  symbol: string;
  name: string;
  exchange: string;
  quantity: number;
  unitCost: number;
  acquiredAt: string | null;
  sourceRowNumber: number | null;
};

export type NormalizedPortfolioImport = {
  format: "pi-portfolio-import/v1";
  portfolioName?: string;
  baseCurrency?: "INR";
  source?: {
    filename?: string;
    sha256?: string;
  };
  holdings: Array<{
    symbol: string;
    name: string;
    exchange: string;
    quantity: number;
    average_cost: number;
    current_price: number;
    analysis_symbol?: string | null;
  }>;
  lots?: Array<{
    symbol: string;
    name: string;
    exchange: string;
    quantity: number;
    unit_cost: number;
    acquired_at: string | null;
    source_row_number: number | null;
  }>;
};

export type ChatResponse = {
  answer: string;
  intent: string;
  status: "grounded" | "restricted";
  evidence: Evidence[];
  citations: ChatCitation[];
  presentation: ChatPresentation;
  asOf: string;
  engine: "llm" | "deterministic" | "deterministic-fallback";
  model?: string;
  researchMode: "portfolio" | "trusted-web";
  fallbackReason?: string;
};

export type ChatCitation = {
  title: string;
  url: string;
  domain: string;
  sourceType: "portfolio" | "web";
};

export type ChatPresentation = {
  title: string;
  kpis: Array<{
    label: string;
    value: string;
    detail: string;
    tone: "positive" | "negative" | "neutral";
  }>;
  table?: {
    title: string;
    columns: string[];
    rows: string[][];
  };
  chart?: {
    type: "bar" | "line";
    title: string;
    unit: "percent" | "currency" | "index";
    categories: string[];
    series: Array<{ name: string; values: Array<number | null> }>;
  };
  note?: string;
};

export type EmailImportStatus = {
  promptStatus: "pending" | "saved" | "dismissed";
  wealthManagerEmail: string | null;
  consentedAt: string | null;
  googleConfigured: boolean;
  mailboxStatus: "not_connected" | "connected" | "expired" | "action_required";
  lastSyncedAt: string | null;
  importedCount: number;
  pendingReviewCount: number;
  detail: string;
};

export type AgentPolicy = {
  reserveFloorInr: number;
  deployableCashInr: number;
  maxPositionWeightPercent: number;
  maxSingleDeploymentInr: number;
  dataMaxAgeMinutes: number;
  noEqualWeighting: true;
  requireHumanConfirmation: true;
};

export type AgentPolicyCheck = {
  code: string;
  severity: "pass" | "warning" | "block";
  message: string;
  symbol?: string | null;
};

export type AgentRunEvent = {
  sequence: number;
  occurred_at: string;
  level: "info" | "warning" | "error";
  stage: string;
  message: string;
  symbol?: string | null;
};

export type AgentSymbolResult = {
  symbol: string;
  analysis_symbol: string;
  rating: "BULLISH" | "BEARISH" | "NEUTRAL" | "ABSTAIN" | "Buy" | "Overweight" | "Hold" | "Underweight" | "Sell" | "Unknown";
  executive_summary: string;
  investment_thesis: string;
  trader_action: "Buy" | "Hold" | "Sell" | "Unknown" | "No action";
  trader_reasoning: string;
  research_judgement: string;
  risk_judgement: string;
  policy_checks: AgentPolicyCheck[];
  reports: Record<string, string>;
};

export type AgentRun = {
  id: string;
  portfolio_id: string;
  snapshot_id: string;
  mode: "review" | "weekly_trigger";
  status: "queued" | "running" | "completed" | "blocked" | "failed";
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  selected_symbols: string[];
  policy_checks: AgentPolicyCheck[];
  results: AgentSymbolResult[];
  error: string | null;
  last_event_sequence: number;
  workflow_engine: "langgraph" | "tradingagents-adapter";
  workflow_version: string;
  events?: AgentRunEvent[];
};

export type AgentRuntimeStatus = {
  configured: boolean;
  reachable: boolean;
  runtime: "tradingagents";
  mode: "external" | "demo_safe";
  version: string | null;
  detail: string;
};
