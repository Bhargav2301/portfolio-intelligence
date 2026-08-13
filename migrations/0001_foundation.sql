CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    jurisdiction TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE portfolios (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    name TEXT NOT NULL,
    portfolio_type TEXT NOT NULL CHECK (portfolio_type IN ('owned', 'pms', 'model', 'interest')),
    base_currency CHAR(3) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (user_id, name)
);

CREATE TABLE instruments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    asset_type TEXT NOT NULL,
    canonical_symbol TEXT NOT NULL,
    isin TEXT,
    mic TEXT,
    chain_id TEXT,
    contract_address TEXT,
    currency CHAR(3) NOT NULL
);

CREATE UNIQUE INDEX instruments_isin_mic_unique
    ON instruments (isin, mic)
    WHERE isin IS NOT NULL;

CREATE UNIQUE INDEX instruments_chain_contract_unique
    ON instruments (chain_id, contract_address)
    WHERE chain_id IS NOT NULL AND contract_address IS NOT NULL;

CREATE TABLE transactions (
    id UUID PRIMARY KEY,
    portfolio_id UUID NOT NULL REFERENCES portfolios(id),
    instrument_id UUID NOT NULL REFERENCES instruments(id),
    transaction_type TEXT NOT NULL CHECK (transaction_type IN ('buy', 'sell', 'dividend', 'fee', 'reversal')),
    quantity NUMERIC(28, 10) NOT NULL,
    unit_price NUMERIC(28, 10) NOT NULL,
    fees NUMERIC(28, 10) NOT NULL DEFAULT 0,
    currency CHAR(3) NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    idempotency_key TEXT NOT NULL UNIQUE,
    reverses_transaction_id UUID REFERENCES transactions(id),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX transactions_portfolio_time_idx
    ON transactions (portfolio_id, occurred_at, recorded_at);

CREATE TABLE price_observations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    instrument_id UUID NOT NULL REFERENCES instruments(id),
    price NUMERIC(28, 10) NOT NULL CHECK (price >= 0),
    currency CHAR(3) NOT NULL,
    source TEXT NOT NULL,
    effective_at TIMESTAMPTZ NOT NULL,
    received_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    content_hash CHAR(64) NOT NULL,
    UNIQUE (instrument_id, source, effective_at)
);

CREATE TABLE evidence_items (
    id UUID PRIMARY KEY,
    instrument_id UUID REFERENCES instruments(id),
    source_tier SMALLINT NOT NULL CHECK (source_tier BETWEEN 1 AND 4),
    publisher TEXT NOT NULL,
    source_uri TEXT NOT NULL,
    title TEXT NOT NULL,
    published_at TIMESTAMPTZ NOT NULL,
    retrieved_at TIMESTAMPTZ NOT NULL,
    content_hash CHAR(64) NOT NULL,
    content_excerpt TEXT NOT NULL,
    entitlement TEXT NOT NULL,
    UNIQUE (source_uri, content_hash)
);

CREATE TABLE claims (
    id UUID PRIMARY KEY,
    evidence_id UUID NOT NULL REFERENCES evidence_items(id),
    claim_text TEXT NOT NULL,
    excerpt_start INTEGER,
    excerpt_end INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE recommendations (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id),
    portfolio_id UUID REFERENCES portfolios(id),
    instrument_id UUID NOT NULL REFERENCES instruments(id),
    classification TEXT NOT NULL,
    requested_stance TEXT NOT NULL,
    final_stance TEXT NOT NULL,
    as_of TIMESTAMPTZ NOT NULL,
    model_version TEXT NOT NULL,
    policy_version TEXT NOT NULL,
    evidence_ids UUID[] NOT NULL DEFAULT '{}',
    reasons JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE audit_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    event_type TEXT NOT NULL,
    aggregate_type TEXT NOT NULL,
    aggregate_id UUID,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX audit_events_aggregate_idx
    ON audit_events (aggregate_type, aggregate_id, created_at);
