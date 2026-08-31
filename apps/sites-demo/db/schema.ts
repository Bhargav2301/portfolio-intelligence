import { index, integer, real, sqliteTable, text, uniqueIndex } from "drizzle-orm/sqlite-core";

export const portfolios = sqliteTable("portfolios", {
  id: text("id").primaryKey(),
  ownerEmail: text("owner_email").notNull(),
  name: text("name").notNull(),
  baseCurrency: text("base_currency").notNull().default("INR"),
  isDemo: integer("is_demo").notNull().default(1),
  createdAt: text("created_at").notNull(),
}, (table) => [uniqueIndex("portfolios_owner_name_idx").on(table.ownerEmail, table.name)]);

export const transactions = sqliteTable("transactions", {
  id: text("id").primaryKey(),
  portfolioId: text("portfolio_id").notNull().references(() => portfolios.id),
  ownerEmail: text("owner_email").notNull(),
  symbol: text("symbol").notNull(),
  instrumentName: text("instrument_name").notNull(),
  transactionType: text("transaction_type").notNull(),
  quantity: real("quantity").notNull(),
  unitPrice: real("unit_price").notNull(),
  fees: real("fees").notNull().default(0),
  occurredAt: text("occurred_at").notNull(),
  reversesTransactionId: text("reverses_transaction_id"),
  idempotencyKey: text("idempotency_key").notNull(),
  createdAt: text("created_at").notNull(),
}, (table) => [
  uniqueIndex("transactions_idempotency_idx").on(table.idempotencyKey),
  index("transactions_owner_portfolio_time_idx").on(table.ownerEmail, table.portfolioId, table.occurredAt),
]);

export const prices = sqliteTable("prices", {
  symbol: text("symbol").primaryKey(),
  instrumentName: text("instrument_name").notNull(),
  price: real("price").notNull(),
  previousClose: real("previous_close").notNull(),
  sourceLabel: text("source_label").notNull(),
  sourceUri: text("source_uri").notNull(),
  asOf: text("as_of").notNull(),
  currency: text("currency").notNull(),
});

export const evidenceItems = sqliteTable("evidence_items", {
  id: text("id").primaryKey(),
  symbol: text("symbol").notNull(),
  title: text("title").notNull(),
  publisher: text("publisher").notNull(),
  sourceTier: integer("source_tier").notNull(),
  sourceUri: text("source_uri").notNull(),
  publishedAt: text("published_at").notNull(),
  retrievedAt: text("retrieved_at").notNull(),
  contentHash: text("content_hash").notNull(),
  summary: text("summary").notNull(),
  status: text("status").notNull(),
}, (table) => [uniqueIndex("evidence_source_hash_idx").on(table.sourceUri, table.contentHash)]);

export const portfolioPrices = sqliteTable("portfolio_prices", {
  id: text("id").primaryKey(),
  portfolioId: text("portfolio_id").notNull().references(() => portfolios.id),
  ownerEmail: text("owner_email").notNull(),
  symbol: text("symbol").notNull(),
  instrumentName: text("instrument_name").notNull(),
  price: real("price").notNull(),
  previousClose: real("previous_close").notNull(),
  sourceLabel: text("source_label").notNull(),
  sourceUri: text("source_uri").notNull(),
  asOf: text("as_of").notNull(),
  currency: text("currency").notNull(),
}, (table) => [
  uniqueIndex("portfolio_prices_portfolio_symbol_idx").on(table.portfolioId, table.symbol),
  index("portfolio_prices_owner_idx").on(table.ownerEmail, table.portfolioId, table.symbol),
]);

export const brokerConnections = sqliteTable("broker_connections", {
  id: text("id").primaryKey(),
  ownerEmail: text("owner_email").notNull(),
  provider: text("provider").notNull(),
  providerUserId: text("provider_user_id"),
  status: text("status").notNull(),
  accessTokenCiphertext: text("access_token_ciphertext").notNull(),
  accessTokenIv: text("access_token_iv").notNull(),
  tokenExpiresAt: text("token_expires_at"),
  lastSyncedAt: text("last_synced_at"),
  createdAt: text("created_at").notNull(),
  updatedAt: text("updated_at").notNull(),
}, (table) => [uniqueIndex("broker_connections_owner_provider_idx").on(table.ownerEmail, table.provider)]);

export const oauthStates = sqliteTable("oauth_states", {
  stateHash: text("state_hash").primaryKey(),
  ownerEmail: text("owner_email").notNull(),
  provider: text("provider").notNull(),
  expiresAt: text("expires_at").notNull(),
  createdAt: text("created_at").notNull(),
});

export const accountHoldings = sqliteTable("account_holdings", {
  id: text("id").primaryKey(),
  connectionId: text("connection_id").notNull().references(() => brokerConnections.id),
  ownerEmail: text("owner_email").notNull(),
  provider: text("provider").notNull(),
  instrumentKey: text("instrument_key").notNull(),
  symbol: text("symbol").notNull(),
  instrumentName: text("instrument_name").notNull(),
  quantity: real("quantity").notNull(),
  averagePrice: real("average_price").notNull(),
  lastPrice: real("last_price").notNull(),
  updatedAt: text("updated_at").notNull(),
}, (table) => [
  uniqueIndex("account_holdings_connection_instrument_idx").on(table.connectionId, table.instrumentKey),
  index("account_holdings_owner_idx").on(table.ownerEmail, table.provider, table.symbol),
]);

export const instrumentMappings = sqliteTable("instrument_mappings", {
  id: text("id").primaryKey(),
  portfolioId: text("portfolio_id").notNull().references(() => portfolios.id),
  ownerEmail: text("owner_email").notNull(),
  symbol: text("symbol").notNull(),
  exchange: text("exchange").notNull(),
  analysisSymbol: text("analysis_symbol"),
  status: text("status").notNull(),
  source: text("source").notNull(),
  updatedAt: text("updated_at").notNull(),
}, (table) => [
  uniqueIndex("instrument_mappings_portfolio_symbol_idx").on(table.portfolioId, table.symbol),
  index("instrument_mappings_owner_idx").on(table.ownerEmail, table.portfolioId, table.symbol),
]);

export const importBatches = sqliteTable("import_batches", {
  id: text("id").primaryKey(),
  ownerEmail: text("owner_email").notNull(),
  portfolioId: text("portfolio_id").references(() => portfolios.id),
  sourceKind: text("source_kind").notNull(),
  sourceFilename: text("source_filename"),
  sourceHash: text("source_hash").notNull(),
  status: text("status").notNull(),
  rowCount: integer("row_count").notNull(),
  validRowCount: integer("valid_row_count").notNull(),
  warningCount: integer("warning_count").notNull().default(0),
  errorCount: integer("error_count").notNull().default(0),
  rawRetained: integer("raw_retained").notNull().default(0),
  createdAt: text("created_at").notNull(),
  committedAt: text("committed_at"),
}, (table) => [
  uniqueIndex("import_batches_owner_hash_idx").on(table.ownerEmail, table.sourceHash),
  index("import_batches_owner_created_idx").on(table.ownerEmail, table.createdAt),
]);

export const importRows = sqliteTable("import_rows", {
  id: text("id").primaryKey(),
  batchId: text("batch_id").notNull().references(() => importBatches.id),
  rowNumber: integer("row_number").notNull(),
  rowKind: text("row_kind").notNull(),
  rawJson: text("raw_json"),
  normalizedJson: text("normalized_json"),
  validationStatus: text("validation_status").notNull(),
  validationMessage: text("validation_message"),
}, (table) => [
  uniqueIndex("import_rows_batch_row_idx").on(table.batchId, table.rowNumber),
  index("import_rows_batch_status_idx").on(table.batchId, table.validationStatus),
]);

export const portfolioLots = sqliteTable("portfolio_lots", {
  id: text("id").primaryKey(),
  portfolioId: text("portfolio_id").notNull().references(() => portfolios.id),
  ownerEmail: text("owner_email").notNull(),
  importBatchId: text("import_batch_id").references(() => importBatches.id),
  symbol: text("symbol").notNull(),
  exchange: text("exchange").notNull(),
  instrumentName: text("instrument_name").notNull(),
  quantity: real("quantity").notNull(),
  unitCost: real("unit_cost").notNull(),
  acquiredAt: text("acquired_at"),
  sourceRowNumber: integer("source_row_number"),
  createdAt: text("created_at").notNull(),
}, (table) => [
  index("portfolio_lots_owner_portfolio_symbol_idx").on(table.ownerEmail, table.portfolioId, table.symbol),
  index("portfolio_lots_import_batch_idx").on(table.importBatchId),
]);

export const evidenceDocuments = sqliteTable("evidence_documents", {
  id: text("id").primaryKey(),
  ownerEmail: text("owner_email").notNull(),
  portfolioId: text("portfolio_id").references(() => portfolios.id),
  importBatchId: text("import_batch_id").references(() => importBatches.id),
  sourceFilename: text("source_filename").notNull(),
  mimeType: text("mime_type").notNull(),
  sourceHash: text("source_hash").notNull(),
  symbol: text("symbol"),
  title: text("title").notNull(),
  publisher: text("publisher"),
  publishedAt: text("published_at"),
  storageKey: text("storage_key"),
  status: text("status").notNull(),
  createdAt: text("created_at").notNull(),
}, (table) => [
  uniqueIndex("evidence_documents_owner_hash_idx").on(table.ownerEmail, table.sourceHash),
  index("evidence_documents_owner_portfolio_idx").on(table.ownerEmail, table.portfolioId),
]);
