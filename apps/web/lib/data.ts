import type {
  DashboardData,
  Evidence,
  LedgerTransaction,
  Position,
} from "./types";

type RawTransaction = {
  id: string;
  portfolio_id: string;
  symbol: string;
  instrument_name: string;
  transaction_type: "buy" | "sell" | "reversal";
  quantity: number;
  unit_price: number;
  fees: number;
  occurred_at: string;
  reverses_transaction_id: string | null;
  created_at: string;
};

type RawPrice = {
  symbol: string;
  instrument_name: string;
  price: number;
  previous_close: number;
  source_label: string;
  source_uri: string;
  as_of: string;
  currency: string;
};

type RawEvidence = {
  id: string;
  symbol: string;
  title: string;
  publisher: string;
  source_tier: number;
  source_uri: string;
  published_at: string;
  retrieved_at: string;
  content_hash: string;
  summary: string;
  status: "verified" | "stale" | "conflicting";
};

const DEMO_EMAIL = "demo.user@portfolio.local";
const DEMO_AS_OF = "2026-08-13T05:00:00.000Z";

function database() {
  if (!globalThis.__PI_DB) throw new Error("Portfolio database is unavailable");
  return globalThis.__PI_DB;
}

export function ownerFromRequest(request: Request) {
  return request.headers.get("oai-authenticated-user-email") ?? DEMO_EMAIL;
}

async function ensureSchema() {
  const db = database();
  await db.batch([
    db.prepare(`CREATE TABLE IF NOT EXISTS portfolios (
      id TEXT PRIMARY KEY,
      owner_email TEXT NOT NULL,
      name TEXT NOT NULL,
      base_currency TEXT NOT NULL DEFAULT 'INR',
      is_demo INTEGER NOT NULL DEFAULT 1,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      UNIQUE(owner_email, name)
    )`),
    db.prepare(`CREATE TABLE IF NOT EXISTS transactions (
      id TEXT PRIMARY KEY,
      portfolio_id TEXT NOT NULL,
      owner_email TEXT NOT NULL,
      symbol TEXT NOT NULL,
      instrument_name TEXT NOT NULL,
      transaction_type TEXT NOT NULL CHECK(transaction_type IN ('buy','sell','reversal')),
      quantity REAL NOT NULL,
      unit_price REAL NOT NULL,
      fees REAL NOT NULL DEFAULT 0,
      occurred_at TEXT NOT NULL,
      reverses_transaction_id TEXT,
      idempotency_key TEXT NOT NULL UNIQUE,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY(portfolio_id) REFERENCES portfolios(id),
      FOREIGN KEY(reverses_transaction_id) REFERENCES transactions(id)
    )`),
    db.prepare(`CREATE INDEX IF NOT EXISTS transactions_owner_portfolio_time_idx
      ON transactions(owner_email, portfolio_id, occurred_at, created_at)`),
    db.prepare(`CREATE TABLE IF NOT EXISTS prices (
      symbol TEXT PRIMARY KEY,
      instrument_name TEXT NOT NULL,
      price REAL NOT NULL,
      previous_close REAL NOT NULL,
      source_label TEXT NOT NULL,
      source_uri TEXT NOT NULL,
      as_of TEXT NOT NULL,
      currency TEXT NOT NULL
    )`),
    db.prepare(`CREATE TABLE IF NOT EXISTS evidence_items (
      id TEXT PRIMARY KEY,
      symbol TEXT NOT NULL,
      title TEXT NOT NULL,
      publisher TEXT NOT NULL,
      source_tier INTEGER NOT NULL CHECK(source_tier BETWEEN 1 AND 4),
      source_uri TEXT NOT NULL,
      published_at TEXT NOT NULL,
      retrieved_at TEXT NOT NULL,
      content_hash TEXT NOT NULL,
      summary TEXT NOT NULL,
      status TEXT NOT NULL CHECK(status IN ('verified','stale','conflicting')),
      UNIQUE(source_uri, content_hash)
    )`),
  ]);
}

async function seedReferenceData() {
  const db = database();
  await db.batch([
    db.prepare(`INSERT OR IGNORE INTO prices
      (symbol, instrument_name, price, previous_close, source_label, source_uri, as_of, currency)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?)`)
      .bind("NOVA", "Nova Systems Ltd.", 1628.4, 1601.2, "Demo exchange snapshot", "https://example.com/demo/nova/quote", DEMO_AS_OF, "INR"),
    db.prepare(`INSERT OR IGNORE INTO prices
      (symbol, instrument_name, price, previous_close, source_label, source_uri, as_of, currency)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?)`)
      .bind("AETH", "Aether Renewables Ltd.", 842.15, 851.75, "Demo exchange snapshot", "https://example.com/demo/aeth/quote", DEMO_AS_OF, "INR"),
    db.prepare(`INSERT OR IGNORE INTO prices
      (symbol, instrument_name, price, previous_close, source_label, source_uri, as_of, currency)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?)`)
      .bind("SESH", "Seshadri Consumer Ltd.", 2364.8, 2328.6, "Demo exchange snapshot", "https://example.com/demo/sesh/quote", DEMO_AS_OF, "INR"),
    db.prepare(`INSERT OR IGNORE INTO evidence_items
      (id, symbol, title, publisher, source_tier, source_uri, published_at, retrieved_at, content_hash, summary, status)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`)
      .bind("ev-nova-q1", "NOVA", "Q1 operating update", "Demo Exchange", 1, "https://example.com/demo/nova/q1", "2026-08-12T10:00:00.000Z", DEMO_AS_OF, "026c7ce45b731decd733b3fe6337e3e977a0a32037985844b023764673a76038", "Revenue growth remained positive while operating margin narrowed slightly.", "verified"),
    db.prepare(`INSERT OR IGNORE INTO evidence_items
      (id, symbol, title, publisher, source_tier, source_uri, published_at, retrieved_at, content_hash, summary, status)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`)
      .bind("ev-aeth-order", "AETH", "Material project award", "Demo Exchange", 1, "https://example.com/demo/aeth/order", "2026-08-11T08:30:00.000Z", DEMO_AS_OF, "e347a2e7c907258bef4648f23b56e06db5d58f4e5c3e8a0b5de0ce3da33c863d", "The company disclosed a new renewable infrastructure order with phased execution.", "verified"),
    db.prepare(`INSERT OR IGNORE INTO evidence_items
      (id, symbol, title, publisher, source_tier, source_uri, published_at, retrieved_at, content_hash, summary, status)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`)
      .bind("ev-sesh-results", "SESH", "Audited quarterly results", "Demo Exchange", 1, "https://example.com/demo/sesh/results", "2026-08-10T12:15:00.000Z", DEMO_AS_OF, "08dd64e5944a9ed10f49c07499980790774931745ff63acebe7cbfc5ccf01b19", "Audited results showed stable demand and improved cash conversion.", "verified"),
  ]);
}

async function ensureDemoPortfolio(ownerEmail: string) {
  await ensureSchema();
  await seedReferenceData();
  const db = database();
  const existing = await db.prepare(
    "SELECT id FROM portfolios WHERE owner_email = ? ORDER BY created_at LIMIT 1",
  ).bind(ownerEmail).first<{ id: string }>();
  if (existing) return existing.id;

  const portfolioId = crypto.randomUUID();
  await db.prepare(
    "INSERT INTO portfolios (id, owner_email, name, base_currency, is_demo) VALUES (?, ?, ?, 'INR', 1)",
  ).bind(portfolioId, ownerEmail, "India Growth Demo").run();

  const seeds = [
    ["NOVA", "Nova Systems Ltd.", 80, 1450, 120, "2026-05-06T05:00:00.000Z"],
    ["AETH", "Aether Renewables Ltd.", 120, 895, 180, "2026-05-21T05:00:00.000Z"],
    ["SESH", "Seshadri Consumer Ltd.", 50, 2180, 150, "2026-06-03T05:00:00.000Z"],
  ] as const;
  await db.batch(seeds.map(([symbol, name, quantity, price, fees, occurredAt], index) =>
    db.prepare(`INSERT INTO transactions
      (id, portfolio_id, owner_email, symbol, instrument_name, transaction_type, quantity, unit_price, fees, occurred_at, idempotency_key)
      VALUES (?, ?, ?, ?, ?, 'buy', ?, ?, ?, ?, ?)`)
      .bind(crypto.randomUUID(), portfolioId, ownerEmail, symbol, name, quantity, price, fees, occurredAt, `seed-${portfolioId}-${index}`),
  ));
  return portfolioId;
}

async function loadTransactions(ownerEmail: string, portfolioId: string) {
  const result = await database().prepare(`SELECT id, portfolio_id, symbol, instrument_name,
    transaction_type, quantity, unit_price, fees, occurred_at, reverses_transaction_id, created_at
    FROM transactions WHERE owner_email = ? AND portfolio_id = ?
    ORDER BY occurred_at ASC, created_at ASC, id ASC`)
    .bind(ownerEmail, portfolioId).all<RawTransaction>();
  return result.results;
}

function foldPositions(transactions: RawTransaction[], prices: Map<string, RawPrice>) {
  const reversedIds = new Set(
    transactions.filter((row) => row.transaction_type === "reversal")
      .map((row) => row.reverses_transaction_id)
      .filter((id): id is string => Boolean(id)),
  );
  const state = new Map<string, { name: string; quantity: number; costBasis: number; realized: number }>();

  for (const row of transactions) {
    if (row.transaction_type === "reversal" || reversedIds.has(row.id)) continue;
    const current = state.get(row.symbol) ?? { name: row.instrument_name, quantity: 0, costBasis: 0, realized: 0 };
    if (row.transaction_type === "buy") {
      current.quantity += row.quantity;
      current.costBasis += row.quantity * row.unit_price + row.fees;
    } else {
      if (row.quantity > current.quantity + 1e-8) {
        throw new Error(`Sale would create a negative ${row.symbol} position`);
      }
      const averageCost = current.quantity ? current.costBasis / current.quantity : 0;
      current.quantity -= row.quantity;
      current.costBasis -= averageCost * row.quantity;
      current.realized += row.quantity * row.unit_price - row.fees - averageCost * row.quantity;
    }
    state.set(row.symbol, current);
  }

  const preliminary = [...state.entries()].filter(([, value]) => value.quantity > 1e-8).map(([symbol, value]) => {
    const price = prices.get(symbol);
    const currentPrice = price?.price ?? 0;
    const marketValue = value.quantity * currentPrice;
    const unrealizedGain = marketValue - value.costBasis;
    return {
      symbol,
      name: value.name,
      quantity: value.quantity,
      averageCost: value.quantity ? value.costBasis / value.quantity : 0,
      currentPrice,
      marketValue,
      costBasis: value.costBasis,
      unrealizedGain,
      returnPercent: value.costBasis ? (unrealizedGain / value.costBasis) * 100 : 0,
      allocationPercent: 0,
      priceSource: price?.source_label ?? "No current price",
      priceAsOf: price?.as_of ?? DEMO_AS_OF,
    } satisfies Position;
  });
  const totalValue = preliminary.reduce((sum, position) => sum + position.marketValue, 0);
  return preliminary.map((position) => ({
    ...position,
    allocationPercent: totalValue ? (position.marketValue / totalValue) * 100 : 0,
  })).sort((a, b) => b.marketValue - a.marketValue);
}

export async function getDashboard(ownerEmail: string): Promise<DashboardData> {
  const portfolioId = await ensureDemoPortfolio(ownerEmail);
  const db = database();
  const [portfolio, priceResult, evidenceResult, transactions] = await Promise.all([
    db.prepare("SELECT id, name, base_currency, is_demo FROM portfolios WHERE id = ? AND owner_email = ?")
      .bind(portfolioId, ownerEmail).first<{ id: string; name: string; base_currency: string; is_demo: number }>(),
    db.prepare("SELECT * FROM prices ORDER BY symbol").all<RawPrice>(),
    db.prepare("SELECT * FROM evidence_items ORDER BY published_at DESC").all<RawEvidence>(),
    loadTransactions(ownerEmail, portfolioId),
  ]);
  if (!portfolio) throw new Error("Portfolio was not found");

  const prices = new Map(priceResult.results.map((price) => [price.symbol, price]));
  const positions = foldPositions(transactions, prices);
  const totalValue = positions.reduce((sum, position) => sum + position.marketValue, 0);
  const totalCost = positions.reduce((sum, position) => sum + position.costBasis, 0);
  const totalGain = totalValue - totalCost;
  const previousValue = positions.reduce((sum, position) => {
    const previousClose = prices.get(position.symbol)?.previous_close ?? position.currentPrice;
    return sum + previousClose * position.quantity;
  }, 0);

  const evidence: Evidence[] = evidenceResult.results.map((item) => ({
    id: item.id,
    symbol: item.symbol,
    title: item.title,
    publisher: item.publisher,
    sourceTier: item.source_tier,
    sourceUri: item.source_uri,
    publishedAt: item.published_at,
    summary: item.summary,
    status: item.status,
  }));
  const reversedIds = new Set(transactions.filter((row) => row.transaction_type === "reversal")
    .map((row) => row.reverses_transaction_id).filter((id): id is string => Boolean(id)));
  const ledger: LedgerTransaction[] = [...transactions].reverse().map((row) => ({
    id: row.id,
    symbol: row.symbol,
    name: row.instrument_name,
    type: row.transaction_type,
    quantity: row.quantity,
    unitPrice: row.unit_price,
    fees: row.fees,
    occurredAt: row.occurred_at,
    reversesTransactionId: row.reverses_transaction_id,
    reversed: reversedIds.has(row.id),
  }));

  const historyMultipliers = [0.89, 0.91, 0.9, 0.94, 0.96, 0.955, 0.98, 1.0];
  const labels = ["May 05", "May 19", "Jun 02", "Jun 16", "Jun 30", "Jul 14", "Jul 28", "Aug 13"];

  return {
    portfolio: { id: portfolio.id, name: portfolio.name, baseCurrency: portfolio.base_currency, isDemo: Boolean(portfolio.is_demo) },
    metrics: {
      totalValue,
      totalCost,
      totalGain,
      returnPercent: totalCost ? (totalGain / totalCost) * 100 : 0,
      dayChange: totalValue - previousValue,
      dayChangePercent: previousValue ? ((totalValue - previousValue) / previousValue) * 100 : 0,
      evidenceCoverage: positions.length ? (positions.filter((position) => evidence.some((item) => item.symbol === position.symbol && item.status === "verified")).length / positions.length) * 100 : 0,
    },
    positions,
    transactions: ledger,
    evidence,
    valueHistory: labels.map((label, index) => ({ label, value: totalValue * historyMultipliers[index] })),
    asOf: DEMO_AS_OF,
    sourceMode: "demo",
  };
}

export async function addTransaction(ownerEmail: string, input: {
  symbol: string;
  type: "buy" | "sell";
  quantity: number;
  unitPrice: number;
  fees: number;
  occurredAt: string;
  idempotencyKey: string;
}) {
  const portfolioId = await ensureDemoPortfolio(ownerEmail);
  const price = await database().prepare("SELECT symbol, instrument_name FROM prices WHERE symbol = ?")
    .bind(input.symbol).first<{ symbol: string; instrument_name: string }>();
  if (!price) throw new Error("Choose a supported demo instrument");
  if (!(input.quantity > 0) || !(input.unitPrice >= 0) || !(input.fees >= 0)) {
    throw new Error("Quantity must be positive and financial values cannot be negative");
  }
  const occurredAt = new Date(input.occurredAt);
  if (Number.isNaN(occurredAt.getTime())) throw new Error("Enter a valid transaction date");

  const current = await loadTransactions(ownerEmail, portfolioId);
  const proposed: RawTransaction = {
    id: crypto.randomUUID(), portfolio_id: portfolioId, symbol: price.symbol,
    instrument_name: price.instrument_name, transaction_type: input.type,
    quantity: input.quantity, unit_price: input.unitPrice, fees: input.fees,
    occurred_at: occurredAt.toISOString(), reverses_transaction_id: null,
    created_at: new Date().toISOString(),
  };
  foldPositions([...current, proposed].sort((a, b) => a.occurred_at.localeCompare(b.occurred_at)), new Map());
  await database().prepare(`INSERT INTO transactions
    (id, portfolio_id, owner_email, symbol, instrument_name, transaction_type, quantity, unit_price, fees, occurred_at, idempotency_key)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`)
    .bind(proposed.id, portfolioId, ownerEmail, proposed.symbol, proposed.instrument_name,
      proposed.transaction_type, proposed.quantity, proposed.unit_price, proposed.fees,
      proposed.occurred_at, input.idempotencyKey).run();
  return proposed.id;
}

export async function reverseTransaction(ownerEmail: string, transactionId: string) {
  const portfolioId = await ensureDemoPortfolio(ownerEmail);
  const current = await loadTransactions(ownerEmail, portfolioId);
  const original = current.find((row) => row.id === transactionId && row.transaction_type !== "reversal");
  if (!original) throw new Error("Transaction was not found");
  if (current.some((row) => row.reverses_transaction_id === transactionId)) {
    throw new Error("Transaction is already reversed");
  }
  const reversal: RawTransaction = {
    id: crypto.randomUUID(), portfolio_id: portfolioId, symbol: original.symbol,
    instrument_name: original.instrument_name, transaction_type: "reversal",
    quantity: original.quantity, unit_price: original.unit_price, fees: original.fees,
    occurred_at: new Date().toISOString(), reverses_transaction_id: original.id,
    created_at: new Date().toISOString(),
  };
  foldPositions([...current, reversal], new Map());
  await database().prepare(`INSERT INTO transactions
    (id, portfolio_id, owner_email, symbol, instrument_name, transaction_type, quantity, unit_price, fees, occurred_at, reverses_transaction_id, idempotency_key)
    VALUES (?, ?, ?, ?, ?, 'reversal', ?, ?, ?, ?, ?, ?)`)
    .bind(reversal.id, portfolioId, ownerEmail, reversal.symbol, reversal.instrument_name,
      reversal.quantity, reversal.unit_price, reversal.fees, reversal.occurred_at,
      original.id, `reverse-${original.id}`).run();
  return reversal.id;
}
