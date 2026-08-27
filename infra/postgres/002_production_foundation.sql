CREATE TABLE IF NOT EXISTS users (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    identity_provider_subject varchar(255) NOT NULL UNIQUE,
    email_ciphertext text,
    status varchar(24) NOT NULL DEFAULT 'active',
    locale varchar(16) NOT NULL DEFAULT 'en-IN',
    timezone varchar(64) NOT NULL DEFAULT 'Asia/Kolkata',
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS tenant_memberships (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL REFERENCES tenants(id),
    user_id uuid NOT NULL REFERENCES users(id),
    role varchar(24) NOT NULL DEFAULT 'viewer',
    status varchar(24) NOT NULL DEFAULT 'active',
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_membership_tenant_user UNIQUE (tenant_id, user_id),
    CONSTRAINT ck_membership_role CHECK (role IN ('owner', 'analyst', 'viewer', 'support'))
);
CREATE INDEX IF NOT EXISTS ix_membership_user_status ON tenant_memberships (user_id, status);

ALTER TABLE portfolios ADD COLUMN IF NOT EXISTS ledger_version integer NOT NULL DEFAULT 0;
ALTER TABLE uploads ADD COLUMN IF NOT EXISTS version integer NOT NULL DEFAULT 1;

CREATE TABLE IF NOT EXISTS accounts (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL REFERENCES tenants(id),
    portfolio_id uuid NOT NULL REFERENCES portfolios(id),
    provider varchar(40) NOT NULL DEFAULT 'generic_csv',
    account_type varchar(32) NOT NULL DEFAULT 'brokerage',
    masked_reference varchar(160) NOT NULL,
    currency varchar(3) NOT NULL DEFAULT 'INR',
    status varchar(24) NOT NULL DEFAULT 'active',
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_account_provider_reference UNIQUE (
        tenant_id, portfolio_id, provider, masked_reference
    )
);
CREATE INDEX IF NOT EXISTS ix_accounts_tenant_portfolio ON accounts (tenant_id, portfolio_id);

CREATE TABLE IF NOT EXISTS instruments (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    identifier_type varchar(24) NOT NULL,
    identifier varchar(128) NOT NULL,
    exchange varchar(16) NOT NULL,
    symbol varchar(64) NOT NULL,
    asset_type varchar(32) NOT NULL DEFAULT 'equity',
    currency varchar(3) NOT NULL DEFAULT 'INR',
    status varchar(24) NOT NULL DEFAULT 'active',
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_instrument_identifier UNIQUE (identifier_type, identifier)
);
CREATE INDEX IF NOT EXISTS ix_instruments_exchange_symbol ON instruments (exchange, symbol);

CREATE TABLE IF NOT EXISTS instrument_aliases (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    instrument_id uuid NOT NULL REFERENCES instruments(id),
    provider varchar(40) NOT NULL,
    alias varchar(128) NOT NULL,
    verification_status varchar(24) NOT NULL DEFAULT 'verified',
    valid_from timestamptz,
    valid_to timestamptz,
    CONSTRAINT uq_instrument_alias_provider UNIQUE (provider, alias)
);

CREATE TABLE IF NOT EXISTS documents (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL REFERENCES tenants(id),
    portfolio_id uuid NOT NULL REFERENCES portfolios(id),
    upload_id uuid NOT NULL UNIQUE REFERENCES uploads(id),
    document_family varchar(40) NOT NULL DEFAULT 'generic_ledger_csv',
    state varchar(32) NOT NULL DEFAULT 'quarantined',
    source_hash varchar(64) NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_documents_tenant_portfolio ON documents (tenant_id, portfolio_id);

CREATE TABLE IF NOT EXISTS extraction_runs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL REFERENCES tenants(id),
    document_id uuid NOT NULL REFERENCES documents(id),
    parser_name varchar(80) NOT NULL,
    parser_version varchar(32) NOT NULL,
    template_id varchar(80) NOT NULL,
    state varchar(32) NOT NULL DEFAULT 'running',
    started_at timestamptz NOT NULL DEFAULT now(),
    completed_at timestamptz,
    metrics_json jsonb NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS ix_extraction_document_started
    ON extraction_runs (document_id, started_at DESC);

CREATE TABLE IF NOT EXISTS extracted_records (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL REFERENCES tenants(id),
    extraction_run_id uuid NOT NULL REFERENCES extraction_runs(id),
    source_row integer NOT NULL,
    raw_hash varchar(64) NOT NULL,
    normalized_data jsonb NOT NULL,
    confidence numeric(5,4) NOT NULL DEFAULT 1,
    state varchar(24) NOT NULL DEFAULT 'candidate',
    version integer NOT NULL DEFAULT 1,
    edited_by uuid,
    edited_at timestamptz,
    CONSTRAINT uq_extraction_source_row UNIQUE (extraction_run_id, source_row),
    CONSTRAINT ck_extracted_confidence CHECK (confidence >= 0 AND confidence <= 1),
    CONSTRAINT ck_extracted_version CHECK (version > 0)
);
CREATE INDEX IF NOT EXISTS ix_extracted_tenant_run
    ON extracted_records (tenant_id, extraction_run_id);

CREATE TABLE IF NOT EXISTS mapping_rules (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL REFERENCES tenants(id),
    provider varchar(40) NOT NULL DEFAULT 'generic_csv',
    document_family varchar(40) NOT NULL,
    source_field varchar(80) NOT NULL,
    target_field varchar(80),
    transform_version varchar(32) NOT NULL DEFAULT '1',
    status varchar(24) NOT NULL DEFAULT 'active',
    exclusion_reason varchar(255),
    CONSTRAINT uq_mapping_rule_scope UNIQUE (
        tenant_id, provider, document_family, source_field
    )
);

CREATE TABLE IF NOT EXISTS import_batches (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL REFERENCES tenants(id),
    portfolio_id uuid NOT NULL REFERENCES portfolios(id),
    document_id uuid NOT NULL REFERENCES documents(id),
    extraction_run_id uuid NOT NULL REFERENCES extraction_runs(id),
    state varchar(32) NOT NULL DEFAULT 'draft',
    version integer NOT NULL DEFAULT 1,
    base_ledger_version integer NOT NULL DEFAULT 0,
    content_hash varchar(64) NOT NULL,
    validated_hash varchar(64),
    validation_summary jsonb NOT NULL DEFAULT '{}'::jsonb,
    published_ledger_version integer,
    created_by uuid NOT NULL,
    approved_by uuid,
    published_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_import_batch_content UNIQUE (tenant_id, content_hash),
    CONSTRAINT ck_import_batch_version CHECK (version > 0)
);
CREATE INDEX IF NOT EXISTS ix_import_batch_tenant_portfolio
    ON import_batches (tenant_id, portfolio_id);

CREATE TABLE IF NOT EXISTS import_batch_records (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL REFERENCES tenants(id),
    import_batch_id uuid NOT NULL REFERENCES import_batches(id),
    extracted_record_id uuid NOT NULL REFERENCES extracted_records(id),
    disposition varchar(24) NOT NULL DEFAULT 'pending',
    exclusion_reason varchar(255),
    CONSTRAINT uq_batch_record UNIQUE (import_batch_id, extracted_record_id)
);

CREATE TABLE IF NOT EXISTS reconciliation_cases (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL REFERENCES tenants(id),
    portfolio_id uuid NOT NULL REFERENCES portfolios(id),
    import_batch_id uuid NOT NULL REFERENCES import_batches(id),
    extracted_record_id uuid REFERENCES extracted_records(id),
    kind varchar(48) NOT NULL,
    severity varchar(16) NOT NULL DEFAULT 'error',
    state varchar(24) NOT NULL DEFAULT 'open',
    details jsonb NOT NULL DEFAULT '{}'::jsonb,
    resolution jsonb NOT NULL DEFAULT '{}'::jsonb,
    resolved_by uuid,
    resolved_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_reconciliation_tenant_state
    ON reconciliation_cases (tenant_id, state);

CREATE TABLE IF NOT EXISTS ledger_versions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL REFERENCES tenants(id),
    portfolio_id uuid NOT NULL REFERENCES portfolios(id),
    version integer NOT NULL,
    import_batch_id uuid REFERENCES import_batches(id),
    event_count integer NOT NULL,
    content_hash varchar(64) NOT NULL,
    published_by uuid NOT NULL,
    published_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_ledger_version UNIQUE (tenant_id, portfolio_id, version),
    CONSTRAINT ck_ledger_version_positive CHECK (version > 0)
);
CREATE INDEX IF NOT EXISTS ix_ledger_versions_portfolio
    ON ledger_versions (tenant_id, portfolio_id, version DESC);

ALTER TABLE transactions ADD COLUMN IF NOT EXISTS account_id uuid REFERENCES accounts(id);
ALTER TABLE transactions ADD COLUMN IF NOT EXISTS instrument_id uuid REFERENCES instruments(id);
ALTER TABLE transactions ADD COLUMN IF NOT EXISTS import_batch_id uuid REFERENCES import_batches(id);
ALTER TABLE transactions ADD COLUMN IF NOT EXISTS ledger_version integer NOT NULL DEFAULT 0;
ALTER TABLE transactions ADD COLUMN IF NOT EXISTS fees numeric(28,8) NOT NULL DEFAULT 0;
ALTER TABLE transactions ADD COLUMN IF NOT EXISTS taxes numeric(28,8) NOT NULL DEFAULT 0;
ALTER TABLE transactions ADD COLUMN IF NOT EXISTS cash_delta numeric(28,8);

CREATE TABLE IF NOT EXISTS cash_events (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL REFERENCES tenants(id),
    portfolio_id uuid NOT NULL REFERENCES portfolios(id),
    transaction_id uuid NOT NULL REFERENCES transactions(id),
    import_batch_id uuid REFERENCES import_batches(id),
    event_at timestamptz NOT NULL,
    amount numeric(28,8) NOT NULL,
    currency varchar(3) NOT NULL,
    event_type varchar(32) NOT NULL,
    ledger_version integer NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_cash_events_portfolio_date
    ON cash_events (tenant_id, portfolio_id, event_at DESC);

CREATE TABLE IF NOT EXISTS jobs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL REFERENCES tenants(id),
    job_type varchar(48) NOT NULL,
    state varchar(24) NOT NULL DEFAULT 'queued',
    resource_type varchar(48) NOT NULL,
    resource_id uuid NOT NULL,
    attempts integer NOT NULL DEFAULT 0,
    result jsonb NOT NULL DEFAULT '{}'::jsonb,
    error_code varchar(64),
    trace_id varchar(64),
    created_at timestamptz NOT NULL DEFAULT now(),
    started_at timestamptz,
    completed_at timestamptz
);
CREATE INDEX IF NOT EXISTS ix_jobs_tenant_state ON jobs (tenant_id, state);

CREATE TABLE IF NOT EXISTS idempotency_records (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL REFERENCES tenants(id),
    principal_id uuid NOT NULL,
    endpoint varchar(160) NOT NULL,
    idempotency_key varchar(160) NOT NULL,
    request_hash varchar(64) NOT NULL,
    status_code integer NOT NULL,
    response_body jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    expires_at timestamptz NOT NULL,
    CONSTRAINT uq_idempotency_scope UNIQUE (
        tenant_id, principal_id, endpoint, idempotency_key
    )
);
CREATE INDEX IF NOT EXISTS ix_idempotency_expires ON idempotency_records (expires_at);

CREATE TABLE IF NOT EXISTS outbox_events (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id uuid NOT NULL DEFAULT gen_random_uuid() UNIQUE,
    tenant_id uuid NOT NULL REFERENCES tenants(id),
    event_type varchar(96) NOT NULL,
    event_version integer NOT NULL DEFAULT 1,
    aggregate_type varchar(48) NOT NULL,
    aggregate_id uuid NOT NULL,
    aggregate_version integer NOT NULL,
    trace_id varchar(64),
    payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    occurred_at timestamptz NOT NULL DEFAULT now(),
    published_at timestamptz
);
CREATE INDEX IF NOT EXISTS ix_outbox_pending ON outbox_events (published_at, occurred_at);

CREATE TABLE IF NOT EXISTS agent_proposals (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL REFERENCES tenants(id),
    portfolio_id uuid NOT NULL REFERENCES portfolios(id),
    run_id uuid NOT NULL,
    proposal jsonb NOT NULL DEFAULT '{}'::jsonb,
    can_execute boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT ck_agent_proposal_never_executes CHECK (can_execute = false)
);
CREATE INDEX IF NOT EXISTS ix_agent_proposals_tenant_portfolio
    ON agent_proposals (tenant_id, portfolio_id);

-- Tenant-aware keys make cross-tenant references impossible even if an application query
-- accidentally supplies a valid foreign identifier from another workspace.
ALTER TABLE portfolios ADD CONSTRAINT uq_portfolio_id_tenant UNIQUE (id, tenant_id);
ALTER TABLE uploads ADD CONSTRAINT uq_upload_id_tenant UNIQUE (id, tenant_id);
ALTER TABLE accounts ADD CONSTRAINT uq_account_id_tenant UNIQUE (id, tenant_id);
ALTER TABLE documents ADD CONSTRAINT uq_document_id_tenant UNIQUE (id, tenant_id);
ALTER TABLE extraction_runs ADD CONSTRAINT uq_extraction_id_tenant UNIQUE (id, tenant_id);
ALTER TABLE extracted_records ADD CONSTRAINT uq_extracted_record_id_tenant UNIQUE (id, tenant_id);
ALTER TABLE import_batches ADD CONSTRAINT uq_import_batch_id_tenant UNIQUE (id, tenant_id);
ALTER TABLE transactions ADD CONSTRAINT uq_transaction_id_tenant UNIQUE (id, tenant_id);

ALTER TABLE portfolios ADD CONSTRAINT fk_portfolio_owner_membership
    FOREIGN KEY (tenant_id, owner_user_id)
    REFERENCES tenant_memberships (tenant_id, user_id)
    DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE uploads ADD CONSTRAINT fk_upload_portfolio_tenant
    FOREIGN KEY (portfolio_id, tenant_id)
    REFERENCES portfolios (id, tenant_id)
    DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE accounts ADD CONSTRAINT fk_account_portfolio_tenant
    FOREIGN KEY (portfolio_id, tenant_id)
    REFERENCES portfolios (id, tenant_id)
    DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE documents ADD CONSTRAINT fk_document_portfolio_tenant
    FOREIGN KEY (portfolio_id, tenant_id)
    REFERENCES portfolios (id, tenant_id)
    DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE documents ADD CONSTRAINT fk_document_upload_tenant
    FOREIGN KEY (upload_id, tenant_id)
    REFERENCES uploads (id, tenant_id)
    DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE extraction_runs ADD CONSTRAINT fk_extraction_document_tenant
    FOREIGN KEY (document_id, tenant_id)
    REFERENCES documents (id, tenant_id)
    DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE extracted_records ADD CONSTRAINT fk_extracted_run_tenant
    FOREIGN KEY (extraction_run_id, tenant_id)
    REFERENCES extraction_runs (id, tenant_id)
    DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE import_batches ADD CONSTRAINT fk_batch_portfolio_tenant
    FOREIGN KEY (portfolio_id, tenant_id)
    REFERENCES portfolios (id, tenant_id)
    DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE import_batches ADD CONSTRAINT fk_batch_document_tenant
    FOREIGN KEY (document_id, tenant_id)
    REFERENCES documents (id, tenant_id)
    DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE import_batches ADD CONSTRAINT fk_batch_extraction_tenant
    FOREIGN KEY (extraction_run_id, tenant_id)
    REFERENCES extraction_runs (id, tenant_id)
    DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE import_batch_records ADD CONSTRAINT fk_batch_record_batch_tenant
    FOREIGN KEY (import_batch_id, tenant_id)
    REFERENCES import_batches (id, tenant_id)
    DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE import_batch_records ADD CONSTRAINT fk_batch_record_extracted_tenant
    FOREIGN KEY (extracted_record_id, tenant_id)
    REFERENCES extracted_records (id, tenant_id)
    DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE reconciliation_cases ADD CONSTRAINT fk_case_portfolio_tenant
    FOREIGN KEY (portfolio_id, tenant_id)
    REFERENCES portfolios (id, tenant_id)
    DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE reconciliation_cases ADD CONSTRAINT fk_case_batch_tenant
    FOREIGN KEY (import_batch_id, tenant_id)
    REFERENCES import_batches (id, tenant_id)
    DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE reconciliation_cases ADD CONSTRAINT fk_case_record_tenant
    FOREIGN KEY (extracted_record_id, tenant_id)
    REFERENCES extracted_records (id, tenant_id)
    DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE ledger_versions ADD CONSTRAINT fk_ledger_portfolio_tenant
    FOREIGN KEY (portfolio_id, tenant_id)
    REFERENCES portfolios (id, tenant_id)
    DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE ledger_versions ADD CONSTRAINT fk_ledger_batch_tenant
    FOREIGN KEY (import_batch_id, tenant_id)
    REFERENCES import_batches (id, tenant_id)
    DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE transactions ADD CONSTRAINT fk_transaction_portfolio_tenant
    FOREIGN KEY (portfolio_id, tenant_id)
    REFERENCES portfolios (id, tenant_id)
    DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE transactions ADD CONSTRAINT fk_transaction_account_tenant
    FOREIGN KEY (account_id, tenant_id)
    REFERENCES accounts (id, tenant_id)
    DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE transactions ADD CONSTRAINT fk_transaction_batch_tenant
    FOREIGN KEY (import_batch_id, tenant_id)
    REFERENCES import_batches (id, tenant_id)
    DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE transactions ADD CONSTRAINT fk_transaction_reversal_tenant
    FOREIGN KEY (reversal_of_id, tenant_id)
    REFERENCES transactions (id, tenant_id)
    DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE cash_events ADD CONSTRAINT fk_cash_portfolio_tenant
    FOREIGN KEY (portfolio_id, tenant_id)
    REFERENCES portfolios (id, tenant_id)
    DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE cash_events ADD CONSTRAINT fk_cash_transaction_tenant
    FOREIGN KEY (transaction_id, tenant_id)
    REFERENCES transactions (id, tenant_id)
    DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE cash_events ADD CONSTRAINT fk_cash_batch_tenant
    FOREIGN KEY (import_batch_id, tenant_id)
    REFERENCES import_batches (id, tenant_id)
    DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE agent_proposals ADD CONSTRAINT fk_agent_proposal_portfolio_tenant
    FOREIGN KEY (portfolio_id, tenant_id)
    REFERENCES portfolios (id, tenant_id)
    DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE tenant_memberships ENABLE ROW LEVEL SECURITY;
ALTER TABLE accounts ENABLE ROW LEVEL SECURITY;
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE extraction_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE extracted_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE mapping_rules ENABLE ROW LEVEL SECURITY;
ALTER TABLE import_batches ENABLE ROW LEVEL SECURITY;
ALTER TABLE import_batch_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE reconciliation_cases ENABLE ROW LEVEL SECURITY;
ALTER TABLE ledger_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE cash_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE idempotency_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE outbox_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_proposals ENABLE ROW LEVEL SECURITY;

ALTER TABLE users FORCE ROW LEVEL SECURITY;
ALTER TABLE tenant_memberships FORCE ROW LEVEL SECURITY;
ALTER TABLE accounts FORCE ROW LEVEL SECURITY;
ALTER TABLE documents FORCE ROW LEVEL SECURITY;
ALTER TABLE extraction_runs FORCE ROW LEVEL SECURITY;
ALTER TABLE extracted_records FORCE ROW LEVEL SECURITY;
ALTER TABLE mapping_rules FORCE ROW LEVEL SECURITY;
ALTER TABLE import_batches FORCE ROW LEVEL SECURITY;
ALTER TABLE import_batch_records FORCE ROW LEVEL SECURITY;
ALTER TABLE reconciliation_cases FORCE ROW LEVEL SECURITY;
ALTER TABLE ledger_versions FORCE ROW LEVEL SECURITY;
ALTER TABLE cash_events FORCE ROW LEVEL SECURITY;
ALTER TABLE jobs FORCE ROW LEVEL SECURITY;
ALTER TABLE idempotency_records FORCE ROW LEVEL SECURITY;
ALTER TABLE outbox_events FORCE ROW LEVEL SECURITY;
ALTER TABLE agent_proposals FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS user_self_access ON users;
CREATE POLICY user_self_access ON users
    USING (id = NULLIF(current_setting('app.current_user', true), '')::uuid)
    WITH CHECK (id = NULLIF(current_setting('app.current_user', true), '')::uuid);

DROP POLICY IF EXISTS tenant_isolation_memberships ON tenant_memberships;
CREATE POLICY tenant_isolation_memberships ON tenant_memberships
    USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid)
    WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);

DO $policies$
DECLARE
    table_name text;
BEGIN
    FOREACH table_name IN ARRAY ARRAY[
        'accounts', 'documents', 'extraction_runs', 'extracted_records', 'mapping_rules',
        'import_batches', 'import_batch_records', 'reconciliation_cases', 'ledger_versions',
        'cash_events', 'jobs', 'idempotency_records', 'outbox_events', 'agent_proposals'
    ] LOOP
        EXECUTE format('DROP POLICY IF EXISTS tenant_isolation_%I ON %I', table_name, table_name);
        EXECUTE format(
            'CREATE POLICY tenant_isolation_%I ON %I '
            'USING (tenant_id = NULLIF(current_setting(''app.current_tenant'', true), '''')::uuid) '
            'WITH CHECK (tenant_id = NULLIF(current_setting(''app.current_tenant'', true), '''')::uuid)',
            table_name, table_name
        );
    END LOOP;
END
$policies$;

DROP TRIGGER IF EXISTS ledger_versions_append_only ON ledger_versions;
CREATE TRIGGER ledger_versions_append_only
    BEFORE UPDATE OR DELETE ON ledger_versions
    FOR EACH ROW EXECUTE FUNCTION prevent_append_only_mutation();

DROP TRIGGER IF EXISTS cash_events_append_only ON cash_events;
CREATE TRIGGER cash_events_append_only
    BEFORE UPDATE OR DELETE ON cash_events
    FOR EACH ROW EXECUTE FUNCTION prevent_append_only_mutation();

DROP TRIGGER IF EXISTS outbox_events_delete_prohibited ON outbox_events;
CREATE TRIGGER outbox_events_delete_prohibited
    BEFORE DELETE ON outbox_events
    FOR EACH ROW EXECUTE FUNCTION prevent_append_only_mutation();

COMMENT ON TABLE ledger_versions IS
    'Immutable publication receipts; corrections create a later compensating ledger version.';
COMMENT ON COLUMN agent_proposals.can_execute IS
    'Hard invariant: AI output is proposal-only and can never authorize broker execution.';
