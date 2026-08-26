import type {
  BrokerConnection,
  DashboardData,
  Evidence,
  HoldingInput,
  LedgerTransaction,
  PortfolioResponse,
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

type RawConnection = {
  id: string;
  provider: "upstox" | "zerodha";
  status: "connected" | "expired" | "action_required";
  token_expires_at: string | null;
  last_synced_at: string | null;
};

type RawAccountHolding = {
  symbol: string;
  instrument_name: string;
  quantity: number;
  average_price: number;
  last_price: number;
  updated_at: string;
};

type RawInstrumentMapping = {
  symbol: string;
  exchange: string;
  analysis_symbol: string | null;
  status: "confirmed" | "unresolved" | "unavailable";
};

const DEMO_EMAIL = "demo.user@portfolio.local";
const DEMO_AS_OF = "2026-08-13T05:00:00.000Z";

function database() {
  if (!globalThis.__PI_DB) throw new Error("Portfolio database is unavailable");
  return globalThis.__PI_DB;
}

export function ownerFromRequest(request: Request) {
  const email = request.headers.get("oai-authenticated-user-email");
  if (email) return email;
  const hostname = new URL(request.url).hostname;
  if (hostname === "terminal.local" || hostname === "localhost") return DEMO_EMAIL;
  throw new Error("AUTHENTICATION_REQUIRED");
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
    db.prepare(`CREATE TABLE IF NOT EXISTS portfolio_prices (
      id TEXT PRIMARY KEY,
      portfolio_id TEXT NOT NULL,
      owner_email TEXT NOT NULL,
      symbol TEXT NOT NULL,
      instrument_name TEXT NOT NULL,
      price REAL NOT NULL,
      previous_close REAL NOT NULL,
      source_label TEXT NOT NULL,
      source_uri TEXT NOT NULL,
      as_of TEXT NOT NULL,
      currency TEXT NOT NULL,
      FOREIGN KEY(portfolio_id) REFERENCES portfolios(id),
      UNIQUE(portfolio_id, symbol)
    )`),
    db.prepare(`CREATE INDEX IF NOT EXISTS portfolio_prices_owner_idx
      ON portfolio_prices(owner_email, portfolio_id, symbol)`),
    db.prepare(`CREATE TABLE IF NOT EXISTS broker_connections (
      id TEXT PRIMARY KEY,
      owner_email TEXT NOT NULL,
      provider TEXT NOT NULL CHECK(provider IN ('upstox','zerodha')),
      provider_user_id TEXT,
      status TEXT NOT NULL CHECK(status IN ('connected','expired','action_required')),
      access_token_ciphertext TEXT NOT NULL,
      access_token_iv TEXT NOT NULL,
      token_expires_at TEXT,
      last_synced_at TEXT,
      created_at TEXT NOT NULL,
      updated_at TEXT NOT NULL,
      UNIQUE(owner_email, provider)
    )`),
    db.prepare(`CREATE TABLE IF NOT EXISTS oauth_states (
      state_hash TEXT PRIMARY KEY,
      owner_email TEXT NOT NULL,
      provider TEXT NOT NULL,
      expires_at TEXT NOT NULL,
      created_at TEXT NOT NULL
    )`),
    db.prepare(`CREATE TABLE IF NOT EXISTS account_holdings (
      id TEXT PRIMARY KEY,
      connection_id TEXT NOT NULL,
      owner_email TEXT NOT NULL,
      provider TEXT NOT NULL,
      instrument_key TEXT NOT NULL,
      symbol TEXT NOT NULL,
      instrument_name TEXT NOT NULL,
      quantity REAL NOT NULL,
      average_price REAL NOT NULL,
      last_price REAL NOT NULL,
      updated_at TEXT NOT NULL,
      FOREIGN KEY(connection_id) REFERENCES broker_connections(id),
      UNIQUE(connection_id, instrument_key)
    )`),
    db.prepare(`CREATE INDEX IF NOT EXISTS account_holdings_owner_idx
      ON account_holdings(owner_email, provider, symbol)`),
    db.prepare(`CREATE TABLE IF NOT EXISTS instrument_mappings (
      id TEXT PRIMARY KEY,
      portfolio_id TEXT NOT NULL,
      owner_email TEXT NOT NULL,
      symbol TEXT NOT NULL,
      exchange TEXT NOT NULL,
      analysis_symbol TEXT,
      status TEXT NOT NULL CHECK(status IN ('confirmed','unresolved','unavailable')),
      source TEXT NOT NULL,
      updated_at TEXT NOT NULL,
      FOREIGN KEY(portfolio_id) REFERENCES portfolios(id),
      UNIQUE(portfolio_id, symbol)
    )`),
    db.prepare(`CREATE INDEX IF NOT EXISTS instrument_mappings_owner_idx
      ON instrument_mappings(owner_email, portfolio_id, symbol)`),
  ]);
}

function marketDataSymbol(exchange: string, symbol: string) {
  if (exchange === "NSE") return `${symbol}.NS`;
  if (exchange === "BSE") return `${symbol}.BO`;
  if (exchange === "NASDAQ" || exchange === "NYSE") return symbol;
  return null;
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

function connectorConfig() {
  return globalThis.__PI_ENV ?? {};
}

function bytesToBase64Url(bytes: Uint8Array) {
  let binary = "";
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

function base64UrlToBytes(value: string) {
  const padded = value.replace(/-/g, "+").replace(/_/g, "/").padEnd(Math.ceil(value.length / 4) * 4, "=");
  const binary = atob(padded);
  return Uint8Array.from(binary, (character) => character.charCodeAt(0));
}

async function sha256(value: string) {
  return bytesToBase64Url(new Uint8Array(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(value))));
}

async function encryptionKey() {
  const secret = connectorConfig().CONNECTOR_ENCRYPTION_KEY;
  if (!secret || secret.length < 24) throw new Error("CONNECTOR_NOT_CONFIGURED");
  const keyBytes = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(secret));
  return crypto.subtle.importKey("raw", keyBytes, "AES-GCM", false, ["encrypt", "decrypt"]);
}

async function encryptToken(token: string) {
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const ciphertext = await crypto.subtle.encrypt({ name: "AES-GCM", iv }, await encryptionKey(), new TextEncoder().encode(token));
  return { ciphertext: bytesToBase64Url(new Uint8Array(ciphertext)), iv: bytesToBase64Url(iv) };
}

async function decryptToken(ciphertext: string, iv: string) {
  const plaintext = await crypto.subtle.decrypt(
    { name: "AES-GCM", iv: base64UrlToBytes(iv) },
    await encryptionKey(),
    base64UrlToBytes(ciphertext),
  );
  return new TextDecoder().decode(plaintext);
}

function requireUpstoxConfig() {
  const config = connectorConfig();
  if (!config.UPSTOX_CLIENT_ID || !config.UPSTOX_CLIENT_SECRET || !config.UPSTOX_REDIRECT_URI || !config.CONNECTOR_ENCRYPTION_KEY) {
    throw new Error("CONNECTOR_NOT_CONFIGURED");
  }
  return {
    clientId: config.UPSTOX_CLIENT_ID,
    clientSecret: config.UPSTOX_CLIENT_SECRET,
    redirectUri: config.UPSTOX_REDIRECT_URI,
  };
}

function nextUpstoxExpiry() {
  const now = new Date();
  const indiaOffsetMs = 5.5 * 60 * 60 * 1000;
  const indiaNow = new Date(now.getTime() + indiaOffsetMs);
  const expiryIndia = new Date(Date.UTC(
    indiaNow.getUTCFullYear(), indiaNow.getUTCMonth(), indiaNow.getUTCDate(), 3, 30,
  ));
  if (expiryIndia.getTime() <= indiaNow.getTime()) expiryIndia.setUTCDate(expiryIndia.getUTCDate() + 1);
  return new Date(expiryIndia.getTime() - indiaOffsetMs).toISOString();
}

export async function startUpstoxConnection(ownerEmail: string) {
  await ensureSchema();
  const config = requireUpstoxConfig();
  const random = crypto.getRandomValues(new Uint8Array(32));
  const state = bytesToBase64Url(random);
  const now = new Date();
  const expiresAt = new Date(now.getTime() + 10 * 60 * 1000).toISOString();
  await database().prepare(`INSERT INTO oauth_states
    (state_hash, owner_email, provider, expires_at, created_at) VALUES (?, ?, 'upstox', ?, ?)`)
    .bind(await sha256(state), ownerEmail, expiresAt, now.toISOString()).run();
  const url = new URL("https://api.upstox.com/v2/login/authorization/dialog");
  url.searchParams.set("response_type", "code");
  url.searchParams.set("client_id", config.clientId);
  url.searchParams.set("redirect_uri", config.redirectUri);
  url.searchParams.set("state", state);
  return url.toString();
}

export async function completeUpstoxConnection(code: string, state: string) {
  await ensureSchema();
  if (!code || !state) throw new Error("INVALID_OAUTH_CALLBACK");
  const stateHash = await sha256(state);
  const stored = await database().prepare(`SELECT owner_email, expires_at FROM oauth_states
    WHERE state_hash = ? AND provider = 'upstox'`).bind(stateHash)
    .first<{ owner_email: string; expires_at: string }>();
  if (!stored || Date.parse(stored.expires_at) <= Date.now()) throw new Error("INVALID_OAUTH_STATE");
  await database().prepare("DELETE FROM oauth_states WHERE state_hash = ?").bind(stateHash).run();

  const config = requireUpstoxConfig();
  const form = new URLSearchParams({
    code,
    client_id: config.clientId,
    client_secret: config.clientSecret,
    redirect_uri: config.redirectUri,
    grant_type: "authorization_code",
  });
  const response = await fetch("https://api.upstox.com/v2/login/authorization/token", {
    method: "POST",
    headers: { accept: "application/json", "content-type": "application/x-www-form-urlencoded" },
    body: form,
  });
  const payload = await response.json() as { access_token?: string; user_id?: string; message?: string };
  if (!response.ok || !payload.access_token) throw new Error("BROKER_AUTHORIZATION_FAILED");

  const token = await encryptToken(payload.access_token);
  const now = new Date().toISOString();
  await database().prepare(`INSERT INTO broker_connections
    (id, owner_email, provider, provider_user_id, status, access_token_ciphertext, access_token_iv,
     token_expires_at, last_synced_at, created_at, updated_at)
    VALUES (?, ?, 'upstox', ?, 'connected', ?, ?, ?, NULL, ?, ?)
    ON CONFLICT(owner_email, provider) DO UPDATE SET
      provider_user_id = excluded.provider_user_id, status = 'connected',
      access_token_ciphertext = excluded.access_token_ciphertext,
      access_token_iv = excluded.access_token_iv, token_expires_at = excluded.token_expires_at,
      updated_at = excluded.updated_at`)
    .bind(crypto.randomUUID(), stored.owner_email, payload.user_id ?? null, token.ciphertext, token.iv,
      nextUpstoxExpiry(), now, now).run();

  await syncUpstoxHoldings(stored.owner_email);
  return stored.owner_email;
}

type UpstoxHolding = {
  instrument_token?: string;
  trading_symbol?: string;
  quantity?: number;
  average_price?: number;
  last_price?: number;
};

export async function syncUpstoxHoldings(ownerEmail: string) {
  await ensureSchema();
  requireUpstoxConfig();
  const connection = await database().prepare(`SELECT id, access_token_ciphertext, access_token_iv, token_expires_at
    FROM broker_connections WHERE owner_email = ? AND provider = 'upstox'`)
    .bind(ownerEmail).first<{ id: string; access_token_ciphertext: string; access_token_iv: string; token_expires_at: string | null }>();
  if (!connection) throw new Error("BROKER_NOT_CONNECTED");
  if (connection.token_expires_at && Date.parse(connection.token_expires_at) <= Date.now()) {
    await database().prepare("UPDATE broker_connections SET status = 'expired', updated_at = ? WHERE id = ?")
      .bind(new Date().toISOString(), connection.id).run();
    throw new Error("BROKER_SESSION_EXPIRED");
  }

  const accessToken = await decryptToken(connection.access_token_ciphertext, connection.access_token_iv);
  const response = await fetch("https://api.upstox.com/v2/portfolio/long-term-holdings", {
    headers: { accept: "application/json", authorization: `Bearer ${accessToken}` },
  });
  if (response.status === 401 || response.status === 403) {
    await database().prepare("UPDATE broker_connections SET status = 'expired', updated_at = ? WHERE id = ?")
      .bind(new Date().toISOString(), connection.id).run();
    throw new Error("BROKER_SESSION_EXPIRED");
  }
  const payload = await response.json() as { status?: string; data?: UpstoxHolding[] };
  if (!response.ok || !Array.isArray(payload.data)) throw new Error("BROKER_SYNC_FAILED");

  const now = new Date().toISOString();
  if (!await firstPortfolio(ownerEmail)) {
    await database().prepare(`INSERT INTO portfolios
      (id, owner_email, name, base_currency, is_demo, created_at) VALUES (?, ?, 'Upstox Portfolio', 'INR', 0, ?)`)
      .bind(crypto.randomUUID(), ownerEmail, now).run();
  }
  const portfolio = await firstPortfolio(ownerEmail);
  if (!portfolio) throw new Error("PORTFOLIO_SETUP_REQUIRED");
  await database().prepare("DELETE FROM account_holdings WHERE connection_id = ?").bind(connection.id).run();
  const statements = payload.data.flatMap((holding) => {
    const symbol = holding.trading_symbol?.trim().toUpperCase();
    const instrumentKey = holding.instrument_token?.trim();
    const quantity = Number(holding.quantity ?? 0);
    const average = Number(holding.average_price ?? 0);
    const last = Number(holding.last_price ?? 0);
    if (!symbol || !instrumentKey || !Number.isFinite(quantity) || quantity <= 0 || !Number.isFinite(average) || !Number.isFinite(last)) return [];
    const exchange = instrumentKey.startsWith("NSE") ? "NSE" : instrumentKey.startsWith("BSE") ? "BSE" : "UNKNOWN";
    const analysisSymbol = marketDataSymbol(exchange, symbol);
    return [database().prepare(`INSERT INTO account_holdings
      (id, connection_id, owner_email, provider, instrument_key, symbol, instrument_name,
       quantity, average_price, last_price, updated_at)
      VALUES (?, ?, ?, 'upstox', ?, ?, ?, ?, ?, ?, ?)`)
      .bind(crypto.randomUUID(), connection.id, ownerEmail, instrumentKey, symbol, symbol, quantity, average, last, now),
    database().prepare(`INSERT INTO instrument_mappings
      (id, portfolio_id, owner_email, symbol, exchange, analysis_symbol, status, source, updated_at)
      VALUES (?, ?, ?, ?, ?, ?, ?, 'upstox', ?)
      ON CONFLICT(portfolio_id, symbol) DO UPDATE SET exchange = excluded.exchange,
        analysis_symbol = excluded.analysis_symbol, status = excluded.status,
        source = excluded.source, updated_at = excluded.updated_at`)
      .bind(crypto.randomUUID(), portfolio.id, ownerEmail, symbol, exchange, analysisSymbol,
        analysisSymbol ? "confirmed" : "unresolved", now)];
  });
  statements.push(database().prepare(`UPDATE broker_connections
    SET status = 'connected', last_synced_at = ?, updated_at = ? WHERE id = ?`)
    .bind(now, now, connection.id));
  await database().batch(statements);
  return getDashboard(ownerEmail);
}

export async function getConnections(ownerEmail: string): Promise<BrokerConnection[]> {
  await ensureSchema();
  const result = await database().prepare(`SELECT id, provider, status, token_expires_at, last_synced_at
    FROM broker_connections WHERE owner_email = ? ORDER BY provider`)
    .bind(ownerEmail).all<RawConnection>();
  const existing = new Map(result.results.map((row) => [row.provider, row]));
  const config = connectorConfig();
  const now = Date.now();

  return (["upstox", "zerodha"] as const).map((provider) => {
    const row = existing.get(provider);
    const configured = provider === "upstox"
      ? Boolean(config.UPSTOX_CLIENT_ID && config.UPSTOX_CLIENT_SECRET && config.UPSTOX_REDIRECT_URI && config.CONNECTOR_ENCRYPTION_KEY)
      : false;
    const expired = row?.token_expires_at ? Date.parse(row.token_expires_at) <= now : false;
    const status: BrokerConnection["status"] = !row
      ? "not_connected"
      : expired
        ? "expired"
        : row.status;
    return {
      provider,
      label: provider === "upstox" ? "Upstox" : "Zerodha Kite",
      configured,
      status,
      readOnly: true,
      lastSyncedAt: row?.last_synced_at ?? null,
      expiresAt: row?.token_expires_at ?? null,
      detail: provider === "upstox"
        ? configured
          ? "OAuth connection; holdings only, with no order permissions used by PI."
          : "Requires the PI Upstox developer app credentials before connection can begin."
        : "Connector contract prepared; activation follows the first Upstox pilot.",
    };
  });
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
  const createdAt = new Date().toISOString();
  await db.prepare(
    "INSERT INTO portfolios (id, owner_email, name, base_currency, is_demo, created_at) VALUES (?, ?, ?, 'INR', 1, ?)",
  ).bind(portfolioId, ownerEmail, "India Growth Demo", createdAt).run();

  const seeds = [
    ["NOVA", "Nova Systems Ltd.", 80, 1450, 120, "2026-05-06T05:00:00.000Z"],
    ["AETH", "Aether Renewables Ltd.", 120, 895, 180, "2026-05-21T05:00:00.000Z"],
    ["SESH", "Seshadri Consumer Ltd.", 50, 2180, 150, "2026-06-03T05:00:00.000Z"],
  ] as const;
  await db.batch(seeds.map(([symbol, name, quantity, price, fees, occurredAt], index) =>
    db.prepare(`INSERT INTO transactions
      (id, portfolio_id, owner_email, symbol, instrument_name, transaction_type, quantity, unit_price, fees, occurred_at, idempotency_key, created_at)
      VALUES (?, ?, ?, ?, ?, 'buy', ?, ?, ?, ?, ?, ?)`)
      .bind(crypto.randomUUID(), portfolioId, ownerEmail, symbol, name, quantity, price, fees, occurredAt, `seed-${portfolioId}-${index}`, createdAt),
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
      exchange: "UNKNOWN",
      analysisSymbol: null,
      mappingStatus: "unresolved",
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

function combineAccountHoldings(ledgerPositions: Position[], holdings: RawAccountHolding[], prices: Map<string, RawPrice>) {
  const combined = new Map(ledgerPositions.map((position) => [position.symbol, { ...position }]));
  for (const holding of holdings) {
    if (holding.quantity <= 0) continue;
    const existing = combined.get(holding.symbol);
    const brokerCost = holding.quantity * holding.average_price;
    const currentPrice = prices.get(holding.symbol)?.price ?? holding.last_price;
    if (existing) {
      const quantity = existing.quantity + holding.quantity;
      const costBasis = existing.costBasis + brokerCost;
      combined.set(holding.symbol, {
        ...existing,
        quantity,
        costBasis,
        averageCost: quantity ? costBasis / quantity : 0,
        currentPrice,
        marketValue: quantity * currentPrice,
        priceSource: "Linked broker holding",
        priceAsOf: holding.updated_at,
        unrealizedGain: quantity * currentPrice - costBasis,
        returnPercent: costBasis ? ((quantity * currentPrice - costBasis) / costBasis) * 100 : 0,
      });
    } else {
      const marketValue = holding.quantity * currentPrice;
      combined.set(holding.symbol, {
        symbol: holding.symbol,
        name: holding.instrument_name,
        exchange: "UNKNOWN",
        analysisSymbol: null,
        mappingStatus: "unresolved",
        quantity: holding.quantity,
        averageCost: holding.average_price,
        currentPrice,
        marketValue,
        costBasis: brokerCost,
        unrealizedGain: marketValue - brokerCost,
        returnPercent: brokerCost ? ((marketValue - brokerCost) / brokerCost) * 100 : 0,
        allocationPercent: 0,
        priceSource: "Linked broker holding",
        priceAsOf: holding.updated_at,
      });
    }
  }
  const positions = [...combined.values()].sort((a, b) => b.marketValue - a.marketValue);
  const totalValue = positions.reduce((sum, position) => sum + position.marketValue, 0);
  return positions.map((position) => ({
    ...position,
    allocationPercent: totalValue ? (position.marketValue / totalValue) * 100 : 0,
  }));
}

async function firstPortfolio(ownerEmail: string) {
  return database().prepare(
    "SELECT id, name, base_currency, is_demo FROM portfolios WHERE owner_email = ? ORDER BY created_at LIMIT 1",
  ).bind(ownerEmail).first<{ id: string; name: string; base_currency: string; is_demo: number }>();
}

export async function getPortfolioResponse(ownerEmail: string): Promise<PortfolioResponse> {
  await ensureSchema();
  const portfolio = await firstPortfolio(ownerEmail);
  if (!portfolio) {
    return {
      status: "needs_setup",
      connections: await getConnections(ownerEmail),
      supportedCurrencies: ["INR"],
      csvColumns: ["symbol", "name", "exchange", "quantity", "average_cost", "current_price"],
    };
  }
  return getDashboard(ownerEmail);
}

export async function getDashboard(ownerEmail: string): Promise<DashboardData> {
  await ensureSchema();
  await seedReferenceData();
  const db = database();
  const portfolio = await firstPortfolio(ownerEmail);
  if (!portfolio) throw new Error("PORTFOLIO_SETUP_REQUIRED");
  const portfolioId = portfolio.id;
  const [priceResult, evidenceResult, transactions, accountHoldingResult, mappingResult, connections] = await Promise.all([
    portfolio.is_demo
      ? db.prepare("SELECT * FROM prices ORDER BY symbol").all<RawPrice>()
      : db.prepare(`SELECT symbol, instrument_name, price, previous_close, source_label, source_uri, as_of, currency
          FROM portfolio_prices WHERE owner_email = ? AND portfolio_id = ? ORDER BY symbol`)
        .bind(ownerEmail, portfolioId).all<RawPrice>(),
    db.prepare("SELECT * FROM evidence_items ORDER BY published_at DESC").all<RawEvidence>(),
    loadTransactions(ownerEmail, portfolioId),
    db.prepare(`SELECT symbol, instrument_name, quantity, average_price, last_price, updated_at
      FROM account_holdings WHERE owner_email = ? ORDER BY symbol`)
      .bind(ownerEmail).all<RawAccountHolding>(),
    db.prepare(`SELECT symbol, exchange, analysis_symbol, status FROM instrument_mappings
      WHERE owner_email = ? AND portfolio_id = ? ORDER BY symbol`)
      .bind(ownerEmail, portfolioId).all<RawInstrumentMapping>(),
    getConnections(ownerEmail),
  ]);

  const prices = new Map(priceResult.results.map((price) => [price.symbol, price]));
  const mappings = new Map(mappingResult.results.map((mapping) => [mapping.symbol, mapping]));
  const positions = combineAccountHoldings(
    foldPositions(transactions, prices),
    accountHoldingResult.results,
    prices,
  ).map((position) => {
    const mapping = mappings.get(position.symbol);
    return {
      ...position,
      exchange: mapping?.exchange ?? "UNKNOWN",
      analysisSymbol: mapping?.analysis_symbol ?? null,
      mappingStatus: mapping?.status ?? (portfolio.is_demo ? "unavailable" : "unresolved"),
    };
  });
  const totalValue = positions.reduce((sum, position) => sum + position.marketValue, 0);
  const totalCost = positions.reduce((sum, position) => sum + position.costBasis, 0);
  const totalGain = totalValue - totalCost;
  const previousValue = positions.reduce((sum, position) => {
    const previousClose = prices.get(position.symbol)?.previous_close ?? position.currentPrice;
    return sum + previousClose * position.quantity;
  }, 0);

  const evidence: Evidence[] = (portfolio.is_demo ? evidenceResult.results : []).map((item) => ({
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
    status: "ready",
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
    valueHistory: portfolio.is_demo
      ? labels.map((label, index) => ({ label, value: totalValue * historyMultipliers[index] }))
      : [{ label: "Current", value: totalValue }],
    asOf: positions.reduce((latest, position) => position.priceAsOf > latest ? position.priceAsOf : latest, DEMO_AS_OF),
    sourceMode: accountHoldingResult.results.length ? "connected" : portfolio.is_demo ? "demo" : "manual",
    connections,
    agentPolicy: {
      reserveFloorInr: 2_500_000,
      deployableCashInr: 3_000_000,
      maxPositionWeightPercent: 15,
      maxSingleDeploymentInr: 200_000,
      dataMaxAgeMinutes: 4320,
      noEqualWeighting: true,
      requireHumanConfirmation: true,
    },
  };
}

function cleanHolding(input: HoldingInput, index: number): HoldingInput {
  const symbol = input.symbol.trim().toUpperCase();
  const name = input.name.trim();
  const exchange = input.exchange.trim().toUpperCase();
  if (!symbol || !name || !exchange) throw new Error(`Holding ${index + 1} is missing identity fields`);
  if (!Number.isFinite(input.quantity) || input.quantity <= 0) throw new Error(`${symbol}: quantity must be positive`);
  if (!Number.isFinite(input.averageCost) || input.averageCost < 0) throw new Error(`${symbol}: average cost cannot be negative`);
  if (!Number.isFinite(input.currentPrice) || input.currentPrice < 0) throw new Error(`${symbol}: current price cannot be negative`);
  return { symbol, name, exchange, quantity: input.quantity, averageCost: input.averageCost, currentPrice: input.currentPrice };
}

export async function createManualPortfolio(ownerEmail: string, input: {
  name: string;
  baseCurrency: "INR";
  holdings: HoldingInput[];
}) {
  await ensureSchema();
  if (await firstPortfolio(ownerEmail)) throw new Error("A portfolio already exists for this account");
  const name = input.name.trim();
  if (!name || name.length > 80) throw new Error("Enter a portfolio name of 80 characters or fewer");
  if (input.holdings.length < 1 || input.holdings.length > 100) throw new Error("Add between 1 and 100 holdings");
  const holdings = input.holdings.map(cleanHolding);
  const symbols = new Set<string>();
  for (const holding of holdings) {
    const key = `${holding.exchange}:${holding.symbol}`;
    if (symbols.has(key)) throw new Error(`${holding.symbol} appears more than once`);
    symbols.add(key);
  }

  const db = database();
  const portfolioId = crypto.randomUUID();
  const now = new Date().toISOString();
  const statements: D1PreparedStatement[] = [
    db.prepare(`INSERT INTO portfolios
      (id, owner_email, name, base_currency, is_demo, created_at)
      VALUES (?, ?, ?, ?, 0, ?)`)
      .bind(portfolioId, ownerEmail, name, input.baseCurrency, now),
  ];
  holdings.forEach((holding, index) => {
    const analysisSymbol = marketDataSymbol(holding.exchange, holding.symbol);
    statements.push(
      db.prepare(`INSERT INTO transactions
        (id, portfolio_id, owner_email, symbol, instrument_name, transaction_type,
         quantity, unit_price, fees, occurred_at, idempotency_key, created_at)
        VALUES (?, ?, ?, ?, ?, 'buy', ?, ?, 0, ?, ?, ?)`)
        .bind(crypto.randomUUID(), portfolioId, ownerEmail, holding.symbol, holding.name,
          holding.quantity, holding.averageCost, now, `setup-${portfolioId}-${index}`, now),
      db.prepare(`INSERT INTO portfolio_prices
        (id, portfolio_id, owner_email, symbol, instrument_name, price, previous_close, source_label, source_uri, as_of, currency)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'User-provided price', ?, ?, ?)
        ON CONFLICT(portfolio_id, symbol) DO UPDATE SET instrument_name = excluded.instrument_name,
          price = excluded.price, previous_close = excluded.previous_close,
          source_label = excluded.source_label, source_uri = excluded.source_uri,
          as_of = excluded.as_of, currency = excluded.currency`)
        .bind(crypto.randomUUID(), portfolioId, ownerEmail, holding.symbol, holding.name, holding.currentPrice, holding.currentPrice,
          `manual://${holding.exchange}/${holding.symbol}`, now, input.baseCurrency),
      db.prepare(`INSERT INTO instrument_mappings
        (id, portfolio_id, owner_email, symbol, exchange, analysis_symbol, status, source, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'manual', ?)`)
        .bind(crypto.randomUUID(), portfolioId, ownerEmail, holding.symbol, holding.exchange, analysisSymbol,
          analysisSymbol ? "confirmed" : "unresolved", now),
    );
  });
  await db.batch(statements);
  return getDashboard(ownerEmail);
}

export async function createDemoPortfolio(ownerEmail: string) {
  if (await firstPortfolio(ownerEmail)) throw new Error("A portfolio already exists for this account");
  await ensureDemoPortfolio(ownerEmail);
  return getDashboard(ownerEmail);
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
  await ensureSchema();
  const portfolio = await firstPortfolio(ownerEmail);
  if (!portfolio) throw new Error("Complete portfolio setup first");
  const portfolioId = portfolio.id;
  const price = await database().prepare(`SELECT symbol, instrument_name FROM portfolio_prices
      WHERE owner_email = ? AND portfolio_id = ? AND symbol = ?
    UNION SELECT symbol, instrument_name FROM prices WHERE symbol = ?
    UNION SELECT symbol, instrument_name FROM account_holdings WHERE owner_email = ? AND symbol = ? LIMIT 1`)
    .bind(ownerEmail, portfolioId, input.symbol, input.symbol, ownerEmail, input.symbol)
    .first<{ symbol: string; instrument_name: string }>();
  if (!price) throw new Error("Choose an instrument already in this portfolio");
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
    (id, portfolio_id, owner_email, symbol, instrument_name, transaction_type, quantity, unit_price, fees, occurred_at, idempotency_key, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`)
    .bind(proposed.id, portfolioId, ownerEmail, proposed.symbol, proposed.instrument_name,
      proposed.transaction_type, proposed.quantity, proposed.unit_price, proposed.fees,
      proposed.occurred_at, input.idempotencyKey, proposed.created_at).run();
  return proposed.id;
}

export async function reverseTransaction(ownerEmail: string, transactionId: string) {
  await ensureSchema();
  const portfolio = await firstPortfolio(ownerEmail);
  if (!portfolio) throw new Error("Complete portfolio setup first");
  const portfolioId = portfolio.id;
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
    (id, portfolio_id, owner_email, symbol, instrument_name, transaction_type, quantity, unit_price, fees, occurred_at, reverses_transaction_id, idempotency_key, created_at)
    VALUES (?, ?, ?, ?, ?, 'reversal', ?, ?, ?, ?, ?, ?, ?)`)
    .bind(reversal.id, portfolioId, ownerEmail, reversal.symbol, reversal.instrument_name,
      reversal.quantity, reversal.unit_price, reversal.fees, reversal.occurred_at,
      original.id, `reverse-${original.id}`, reversal.created_at).run();
  return reversal.id;
}
