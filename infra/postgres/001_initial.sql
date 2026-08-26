CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS tenants (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name varchar(160) NOT NULL,
    tenant_type varchar(32) NOT NULL DEFAULT 'individual',
    base_currency varchar(3) NOT NULL DEFAULT 'INR',
    status varchar(24) NOT NULL DEFAULT 'active',
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT ck_tenant_currency CHECK (base_currency ~ '^[A-Z]{3}$')
);

CREATE TABLE IF NOT EXISTS portfolios (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL REFERENCES tenants(id),
    owner_user_id uuid NOT NULL,
    name varchar(160) NOT NULL,
    portfolio_type varchar(32) NOT NULL,
    base_currency varchar(3) NOT NULL DEFAULT 'INR',
    benchmark_code varchar(64) NOT NULL,
    valuation_timezone varchar(64) NOT NULL DEFAULT 'Asia/Kolkata',
    status varchar(24) NOT NULL DEFAULT 'active',
    version integer NOT NULL DEFAULT 1,
    rules jsonb NOT NULL DEFAULT '{"equal_weighting_allowed":false,"protected_cash":{"amount":"2500000.00","currency":"INR"},"review_cadence":"weekly"}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_portfolio_tenant_name UNIQUE (tenant_id, name),
    CONSTRAINT ck_portfolio_type CHECK (portfolio_type IN ('self_managed', 'pms', 'model', 'interest')),
    CONSTRAINT ck_portfolio_currency CHECK (base_currency ~ '^[A-Z]{3}$'),
    CONSTRAINT ck_portfolio_version CHECK (version > 0)
);

CREATE INDEX IF NOT EXISTS ix_portfolios_tenant_created
    ON portfolios (tenant_id, created_at DESC);

CREATE TABLE IF NOT EXISTS uploads (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL REFERENCES tenants(id),
    portfolio_id uuid NOT NULL REFERENCES portfolios(id),
    created_by uuid NOT NULL,
    object_key varchar(512) NOT NULL,
    original_name varchar(255) NOT NULL,
    declared_type varchar(160),
    detected_type varchar(64) NOT NULL,
    source_role varchar(40) NOT NULL,
    authority_level varchar(24) NOT NULL,
    size_bytes bigint NOT NULL,
    sha256 varchar(64) NOT NULL,
    state varchar(32) NOT NULL,
    parser_summary jsonb NOT NULL DEFAULT '{}'::jsonb,
    error_code varchar(64),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_upload_content_authority UNIQUE (tenant_id, portfolio_id, sha256, source_role),
    CONSTRAINT ck_upload_size CHECK (size_bytes > 0),
    CONSTRAINT ck_upload_sha256 CHECK (sha256 ~ '^[0-9a-f]{64}$'),
    CONSTRAINT ck_upload_role CHECK (source_role IN ('brokerage_ledger', 'broker_statement', 'pms_statement', 'research', 'manual'))
);

CREATE INDEX IF NOT EXISTS ix_uploads_tenant_portfolio_created
    ON uploads (tenant_id, portfolio_id, created_at DESC);

CREATE TABLE IF NOT EXISTS transactions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL REFERENCES tenants(id),
    portfolio_id uuid NOT NULL REFERENCES portfolios(id),
    event_type varchar(32) NOT NULL,
    trade_date timestamptz NOT NULL,
    instrument_reference varchar(128),
    quantity numeric(28,10),
    price numeric(28,10),
    gross_amount numeric(28,8) NOT NULL,
    currency varchar(3) NOT NULL DEFAULT 'INR',
    source_reference varchar(255) NOT NULL,
    reversal_of_id uuid REFERENCES transactions(id),
    recorded_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_transaction_source_reference UNIQUE (tenant_id, portfolio_id, source_reference),
    CONSTRAINT ck_transaction_currency CHECK (currency ~ '^[A-Z]{3}$')
);

CREATE INDEX IF NOT EXISTS ix_transactions_tenant_portfolio_date
    ON transactions (tenant_id, portfolio_id, trade_date DESC);

CREATE TABLE IF NOT EXISTS audit_events (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL REFERENCES tenants(id),
    actor_id uuid,
    action varchar(96) NOT NULL,
    resource_type varchar(64) NOT NULL,
    resource_id uuid,
    trace_id varchar(64),
    details jsonb NOT NULL DEFAULT '{}'::jsonb,
    occurred_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_audit_tenant_occurred
    ON audit_events (tenant_id, occurred_at DESC);

ALTER TABLE tenants ENABLE ROW LEVEL SECURITY;
ALTER TABLE portfolios ENABLE ROW LEVEL SECURITY;
ALTER TABLE uploads ENABLE ROW LEVEL SECURITY;
ALTER TABLE transactions ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_events ENABLE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation_tenants ON tenants
    USING (id = NULLIF(current_setting('app.current_tenant', true), '')::uuid)
    WITH CHECK (id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);

CREATE POLICY tenant_isolation_portfolios ON portfolios
    USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid)
    WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);

CREATE POLICY tenant_isolation_uploads ON uploads
    USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid)
    WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);

CREATE POLICY tenant_isolation_transactions ON transactions
    USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid)
    WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);

CREATE POLICY tenant_isolation_audit_events ON audit_events
    USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid)
    WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);

COMMENT ON TABLE transactions IS
    'Append-only published portfolio ledger. Corrections use reversal rows; application delete routes are prohibited.';

CREATE OR REPLACE FUNCTION prevent_append_only_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION '% is append-only; insert a compensating event instead', TG_TABLE_NAME
        USING ERRCODE = '55000';
END;
$$;

DROP TRIGGER IF EXISTS transactions_append_only ON transactions;
CREATE TRIGGER transactions_append_only
    BEFORE UPDATE OR DELETE ON transactions
    FOR EACH ROW EXECUTE FUNCTION prevent_append_only_mutation();

DROP TRIGGER IF EXISTS audit_events_append_only ON audit_events;
CREATE TRIGGER audit_events_append_only
    BEFORE UPDATE OR DELETE ON audit_events
    FOR EACH ROW EXECUTE FUNCTION prevent_append_only_mutation();
