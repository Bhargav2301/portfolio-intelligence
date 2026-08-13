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
