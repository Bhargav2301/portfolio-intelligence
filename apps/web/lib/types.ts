export type Position = {
  symbol: string;
  name: string;
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
  valueHistory: Array<{ label: string; value: number }>;
  asOf: string;
  sourceMode: "manual" | "connected" | "demo";
  connections: BrokerConnection[];
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
};

export type ChatResponse = {
  answer: string;
  intent: string;
  status: "grounded" | "restricted";
  evidence: Evidence[];
  asOf: string;
};
