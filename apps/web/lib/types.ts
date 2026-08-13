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
  sourceMode: "demo";
};

export type ChatResponse = {
  answer: string;
  intent: string;
  status: "grounded" | "restricted";
  evidence: Evidence[];
  asOf: string;
};
