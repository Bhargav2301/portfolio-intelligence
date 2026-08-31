-- R2/R3: immutable point-in-time analytics inputs, deterministic outputs, evidence, and runs.
-- Every domain row is tenant-scoped. Agents retain no ledger write grant.

CREATE TABLE IF NOT EXISTS market_data_sets (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL REFERENCES tenants(id),
    portfolio_id uuid NOT NULL REFERENCES portfolios(id),
    provider varchar(80) NOT NULL,
    provider_version varchar(80) NOT NULL,
    rights_basis varchar(24) NOT NULL,
    cutoff_at timestamptz NOT NULL,
    known_at timestamptz NOT NULL,
    content_hash varchar(64) NOT NULL,
    status varchar(24) NOT NULL DEFAULT 'sealed',
    created_by uuid NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_market_data_set_version UNIQUE (
        tenant_id, portfolio_id, provider, provider_version
    ),
    CONSTRAINT uq_market_data_set_id_tenant UNIQUE (id, tenant_id),
    CONSTRAINT ck_market_data_rights CHECK (
        rights_basis IN ('licensed', 'user_provided', 'internal')
    ),
    CONSTRAINT ck_market_data_cutoff CHECK (known_at >= cutoff_at),
    CONSTRAINT ck_market_data_hash CHECK (content_hash ~ '^[0-9a-f]{64}$'),
    CONSTRAINT ck_market_data_status CHECK (status = 'sealed')
);
CREATE INDEX IF NOT EXISTS ix_market_data_sets_cutoff
    ON market_data_sets (tenant_id, portfolio_id, cutoff_at DESC);

CREATE TABLE IF NOT EXISTS price_observations (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL REFERENCES tenants(id),
    market_data_set_id uuid NOT NULL REFERENCES market_data_sets(id),
    instrument_reference varchar(128) NOT NULL,
    observed_at timestamptz NOT NULL,
    known_at timestamptz NOT NULL,
    close_price numeric(28,10) NOT NULL,
    currency varchar(3) NOT NULL DEFAULT 'INR',
    quality varchar(24) NOT NULL DEFAULT 'verified',
    source_hash varchar(64) NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_price_observation UNIQUE (
        market_data_set_id, instrument_reference, observed_at
    ),
    CONSTRAINT uq_price_observation_id_tenant UNIQUE (id, tenant_id),
    CONSTRAINT ck_price_positive CHECK (close_price > 0),
    CONSTRAINT ck_price_time CHECK (known_at >= observed_at),
    CONSTRAINT ck_price_currency CHECK (currency ~ '^[A-Z]{3}$'),
    CONSTRAINT ck_price_quality CHECK (quality IN ('verified', 'estimated')),
    CONSTRAINT ck_price_hash CHECK (source_hash ~ '^[0-9a-f]{64}$')
);
CREATE INDEX IF NOT EXISTS ix_price_observations_lookup
    ON price_observations (
        tenant_id, market_data_set_id, instrument_reference, observed_at DESC
    );

CREATE TABLE IF NOT EXISTS corporate_actions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL REFERENCES tenants(id),
    market_data_set_id uuid NOT NULL REFERENCES market_data_sets(id),
    instrument_reference varchar(128) NOT NULL,
    action_type varchar(32) NOT NULL,
    effective_at timestamptz NOT NULL,
    known_at timestamptz NOT NULL,
    split_factor numeric(28,12),
    cash_amount_per_unit numeric(28,10),
    currency varchar(3) NOT NULL DEFAULT 'INR',
    source_hash varchar(64) NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_corporate_action UNIQUE (
        market_data_set_id, instrument_reference, action_type, effective_at
    ),
    CONSTRAINT uq_corporate_action_id_tenant UNIQUE (id, tenant_id),
    CONSTRAINT ck_corporate_action_shape CHECK (
        (action_type = 'split' AND split_factor > 0 AND cash_amount_per_unit IS NULL)
        OR
        (action_type = 'cash_dividend' AND cash_amount_per_unit >= 0 AND split_factor IS NULL)
    ),
    CONSTRAINT ck_corporate_action_currency CHECK (currency ~ '^[A-Z]{3}$'),
    CONSTRAINT ck_corporate_action_hash CHECK (source_hash ~ '^[0-9a-f]{64}$')
);
CREATE INDEX IF NOT EXISTS ix_corporate_actions_lookup
    ON corporate_actions (
        tenant_id, market_data_set_id, instrument_reference, effective_at
    );

CREATE TABLE IF NOT EXISTS analytics_snapshots (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL REFERENCES tenants(id),
    portfolio_id uuid NOT NULL REFERENCES portfolios(id),
    market_data_set_id uuid NOT NULL REFERENCES market_data_sets(id),
    as_of timestamptz NOT NULL,
    known_at timestamptz NOT NULL,
    ledger_version integer NOT NULL,
    market_data_version varchar(80) NOT NULL,
    methodology_version varchar(40) NOT NULL,
    benchmark_code varchar(64) NOT NULL,
    base_currency varchar(3) NOT NULL,
    input_hash varchar(64) NOT NULL,
    quality_state varchar(24) NOT NULL,
    limitations jsonb NOT NULL DEFAULT '[]'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_analytics_snapshot_inputs UNIQUE (tenant_id, portfolio_id, input_hash),
    CONSTRAINT uq_analytics_snapshot_id_tenant UNIQUE (id, tenant_id),
    CONSTRAINT ck_analytics_ledger_version CHECK (ledger_version >= 0),
    CONSTRAINT ck_analytics_time CHECK (known_at >= as_of),
    CONSTRAINT ck_analytics_hash CHECK (input_hash ~ '^[0-9a-f]{64}$'),
    CONSTRAINT ck_analytics_quality CHECK (
        quality_state IN ('trusted', 'needs_review', 'partial', 'stale')
    )
);
CREATE INDEX IF NOT EXISTS ix_analytics_snapshots_latest
    ON analytics_snapshots (tenant_id, portfolio_id, as_of DESC);

CREATE TABLE IF NOT EXISTS valuation_positions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL REFERENCES tenants(id),
    analytics_snapshot_id uuid NOT NULL REFERENCES analytics_snapshots(id),
    instrument_reference varchar(128) NOT NULL,
    quantity numeric(28,10) NOT NULL,
    cost_basis numeric(28,8) NOT NULL,
    price numeric(28,10),
    price_as_of timestamptz,
    market_value numeric(28,8),
    weight numeric(20,12),
    status varchar(24) NOT NULL DEFAULT 'valued',
    CONSTRAINT uq_valuation_position UNIQUE (
        analytics_snapshot_id, instrument_reference
    ),
    CONSTRAINT uq_valuation_position_id_tenant UNIQUE (id, tenant_id),
    CONSTRAINT ck_valuation_quantity CHECK (quantity >= 0),
    CONSTRAINT ck_valuation_weight CHECK (weight IS NULL OR (weight >= 0 AND weight <= 1)),
    CONSTRAINT ck_valuation_price CHECK (price IS NULL OR price > 0)
);
CREATE INDEX IF NOT EXISTS ix_valuation_positions_snapshot
    ON valuation_positions (tenant_id, analytics_snapshot_id);

CREATE TABLE IF NOT EXISTS metric_values (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL REFERENCES tenants(id),
    analytics_snapshot_id uuid NOT NULL REFERENCES analytics_snapshots(id),
    metric_code varchar(64) NOT NULL,
    dimension_type varchar(32) NOT NULL DEFAULT 'portfolio',
    dimension_id varchar(128) NOT NULL DEFAULT 'portfolio',
    value numeric(28,12),
    unit varchar(24) NOT NULL,
    status varchar(24) NOT NULL DEFAULT 'available',
    details jsonb NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT uq_metric_value_dimension UNIQUE (
        analytics_snapshot_id, metric_code, dimension_type, dimension_id
    ),
    CONSTRAINT uq_metric_value_id_tenant UNIQUE (id, tenant_id),
    CONSTRAINT ck_metric_status CHECK (status IN ('available', 'insufficient_data', 'blocked'))
);
CREATE INDEX IF NOT EXISTS ix_metric_values_snapshot
    ON metric_values (tenant_id, analytics_snapshot_id);

CREATE TABLE IF NOT EXISTS scenario_runs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL REFERENCES tenants(id),
    portfolio_id uuid NOT NULL REFERENCES portfolios(id),
    created_by uuid NOT NULL,
    base_snapshot_id uuid NOT NULL REFERENCES analytics_snapshots(id),
    name varchar(160) NOT NULL,
    status varchar(24) NOT NULL DEFAULT 'completed',
    assumptions jsonb NOT NULL DEFAULT '{}'::jsonb,
    results jsonb NOT NULL DEFAULT '{}'::jsonb,
    constraint_results jsonb NOT NULL DEFAULT '[]'::jsonb,
    engine_version varchar(40) NOT NULL,
    can_execute boolean NOT NULL DEFAULT false,
    input_hash varchar(64) NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_scenario_run_id_tenant UNIQUE (id, tenant_id),
    CONSTRAINT ck_scenario_never_executes CHECK (can_execute = false),
    CONSTRAINT ck_scenario_status CHECK (status IN ('completed', 'blocked')),
    CONSTRAINT ck_scenario_hash CHECK (input_hash ~ '^[0-9a-f]{64}$')
);
CREATE INDEX IF NOT EXISTS ix_scenario_runs_portfolio
    ON scenario_runs (tenant_id, portfolio_id, created_at DESC);

CREATE TABLE IF NOT EXISTS evidence_items (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL REFERENCES tenants(id),
    portfolio_id uuid NOT NULL REFERENCES portfolios(id),
    source_type varchar(40) NOT NULL,
    title varchar(255) NOT NULL,
    publisher varchar(160) NOT NULL,
    published_at timestamptz NOT NULL,
    retrieved_at timestamptz NOT NULL,
    known_at timestamptz NOT NULL,
    content_hash varchar(64) NOT NULL,
    locator jsonb NOT NULL DEFAULT '{}'::jsonb,
    claims jsonb NOT NULL DEFAULT '[]'::jsonb,
    quality varchar(24) NOT NULL DEFAULT 'pending',
    rights_basis varchar(24) NOT NULL,
    cutoff_eligible boolean NOT NULL DEFAULT false,
    created_by uuid NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_evidence_hash UNIQUE (tenant_id, portfolio_id, content_hash),
    CONSTRAINT uq_evidence_item_id_tenant UNIQUE (id, tenant_id),
    CONSTRAINT ck_evidence_time CHECK (
        retrieved_at >= published_at AND known_at >= retrieved_at
    ),
    CONSTRAINT ck_evidence_hash CHECK (content_hash ~ '^[0-9a-f]{64}$'),
    CONSTRAINT ck_evidence_rights CHECK (
        rights_basis IN ('licensed', 'user_provided', 'internal')
    ),
    CONSTRAINT ck_evidence_quality CHECK (quality IN ('reviewed', 'verified')),
    CONSTRAINT ck_evidence_source CHECK (
        source_type IN (
            'market', 'fundamentals', 'news', 'sentiment', 'research',
            'analytics_snapshot', 'portfolio_policy', 'deterministic_monitor'
        )
    )
);
CREATE INDEX IF NOT EXISTS ix_evidence_cutoff
    ON evidence_items (tenant_id, portfolio_id, known_at DESC);

CREATE TABLE IF NOT EXISTS evidence_links (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL REFERENCES tenants(id),
    from_type varchar(40) NOT NULL,
    from_id uuid NOT NULL,
    evidence_item_id uuid NOT NULL REFERENCES evidence_items(id),
    relation varchar(24) NOT NULL DEFAULT 'supports',
    claim_key varchar(128) NOT NULL,
    CONSTRAINT uq_evidence_link UNIQUE (
        tenant_id, from_type, from_id, evidence_item_id, claim_key
    ),
    CONSTRAINT uq_evidence_link_id_tenant UNIQUE (id, tenant_id),
    CONSTRAINT ck_evidence_relation CHECK (
        relation IN ('supports', 'contradicts', 'contextualizes')
    )
);

CREATE TABLE IF NOT EXISTS agent_runs (
    id uuid PRIMARY KEY,
    tenant_id uuid NOT NULL REFERENCES tenants(id),
    portfolio_id uuid NOT NULL REFERENCES portfolios(id),
    thread_id uuid NOT NULL,
    initiated_by uuid NOT NULL,
    request_id varchar(96) NOT NULL,
    question_hash varchar(64) NOT NULL,
    intent varchar(40),
    as_of timestamptz NOT NULL,
    known_at timestamptz NOT NULL,
    graph_version varchar(64) NOT NULL,
    prompt_bundle_version varchar(64) NOT NULL,
    model_route varchar(80) NOT NULL,
    policy_version varchar(64) NOT NULL,
    allowed_tools jsonb NOT NULL DEFAULT '[]'::jsonb,
    checkpoint_thread_id varchar(255) NOT NULL,
    state varchar(24) NOT NULL DEFAULT 'running',
    stages jsonb NOT NULL DEFAULT '[]'::jsonb,
    citations jsonb NOT NULL DEFAULT '[]'::jsonb,
    policy jsonb NOT NULL DEFAULT '{}'::jsonb,
    result_hash varchar(64),
    error_code varchar(64),
    can_execute boolean NOT NULL DEFAULT false,
    started_at timestamptz NOT NULL DEFAULT now(),
    completed_at timestamptz,
    CONSTRAINT uq_agent_run_id_tenant UNIQUE (id, tenant_id),
    CONSTRAINT uq_agent_run_request UNIQUE (tenant_id, request_id),
    CONSTRAINT ck_agent_run_never_executes CHECK (can_execute = false),
    CONSTRAINT ck_agent_run_question_hash CHECK (question_hash ~ '^[0-9a-f]{64}$'),
    CONSTRAINT ck_agent_run_result_hash CHECK (
        result_hash IS NULL OR result_hash ~ '^[0-9a-f]{64}$'
    ),
    CONSTRAINT ck_agent_run_time CHECK (known_at >= as_of),
    CONSTRAINT ck_agent_run_completed_time CHECK (
        completed_at IS NULL OR completed_at >= started_at
    ),
    CONSTRAINT ck_agent_run_state CHECK (
        state IN ('running', 'completed', 'failed', 'timed_out')
    ),
    CONSTRAINT ck_agent_run_completion_shape CHECK (
        (
            state = 'running'
            AND completed_at IS NULL
            AND result_hash IS NULL
            AND error_code IS NULL
        )
        OR
        (
            state = 'completed'
            AND completed_at IS NOT NULL
            AND result_hash IS NOT NULL
            AND error_code IS NULL
        )
        OR
        (
            state IN ('failed', 'timed_out')
            AND completed_at IS NOT NULL
            AND result_hash IS NULL
            AND error_code IS NOT NULL
        )
    )
);
CREATE INDEX IF NOT EXISTS ix_agent_runs_portfolio
    ON agent_runs (tenant_id, portfolio_id, started_at DESC);
CREATE INDEX IF NOT EXISTS ix_agent_runs_thread
    ON agent_runs (tenant_id, thread_id, started_at DESC);

CREATE TABLE IF NOT EXISTS agent_run_steps (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL REFERENCES tenants(id),
    agent_run_id uuid NOT NULL REFERENCES agent_runs(id),
    node_name varchar(80) NOT NULL,
    attempt integer NOT NULL DEFAULT 1,
    state varchar(24) NOT NULL DEFAULT 'completed',
    public_summary varchar(255) NOT NULL,
    completed_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_agent_run_step UNIQUE (agent_run_id, node_name, attempt),
    CONSTRAINT uq_agent_run_step_id_tenant UNIQUE (id, tenant_id),
    CONSTRAINT ck_agent_step_attempt CHECK (attempt > 0),
    CONSTRAINT ck_agent_step_state CHECK (state IN ('completed', 'failed', 'timed_out'))
);
CREATE INDEX IF NOT EXISTS ix_agent_run_steps_run
    ON agent_run_steps (tenant_id, agent_run_id);

CREATE TABLE IF NOT EXISTS agent_run_evidence (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL REFERENCES tenants(id),
    agent_run_id uuid NOT NULL REFERENCES agent_runs(id),
    evidence_item_id uuid NOT NULL REFERENCES evidence_items(id),
    claim_key varchar(128) NOT NULL,
    relation varchar(24) NOT NULL DEFAULT 'supports',
    CONSTRAINT uq_agent_run_evidence UNIQUE (
        agent_run_id, evidence_item_id, claim_key
    ),
    CONSTRAINT uq_agent_run_evidence_id_tenant UNIQUE (id, tenant_id),
    CONSTRAINT ck_agent_run_evidence_relation CHECK (
        relation IN ('supports', 'contradicts', 'contextualizes')
    )
);

-- Composite tenant-aware references prevent valid identifiers from another workspace from being
-- attached to the current tenant even if an application filter regresses.
ALTER TABLE market_data_sets ADD CONSTRAINT fk_market_data_portfolio_tenant
    FOREIGN KEY (portfolio_id, tenant_id) REFERENCES portfolios (id, tenant_id)
    DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE price_observations ADD CONSTRAINT fk_price_dataset_tenant
    FOREIGN KEY (market_data_set_id, tenant_id) REFERENCES market_data_sets (id, tenant_id)
    DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE corporate_actions ADD CONSTRAINT fk_action_dataset_tenant
    FOREIGN KEY (market_data_set_id, tenant_id) REFERENCES market_data_sets (id, tenant_id)
    DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE analytics_snapshots ADD CONSTRAINT fk_analytics_portfolio_tenant
    FOREIGN KEY (portfolio_id, tenant_id) REFERENCES portfolios (id, tenant_id)
    DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE analytics_snapshots ADD CONSTRAINT fk_analytics_dataset_tenant
    FOREIGN KEY (market_data_set_id, tenant_id) REFERENCES market_data_sets (id, tenant_id)
    DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE valuation_positions ADD CONSTRAINT fk_valuation_snapshot_tenant
    FOREIGN KEY (analytics_snapshot_id, tenant_id) REFERENCES analytics_snapshots (id, tenant_id)
    DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE metric_values ADD CONSTRAINT fk_metric_snapshot_tenant
    FOREIGN KEY (analytics_snapshot_id, tenant_id) REFERENCES analytics_snapshots (id, tenant_id)
    DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE scenario_runs ADD CONSTRAINT fk_scenario_portfolio_tenant
    FOREIGN KEY (portfolio_id, tenant_id) REFERENCES portfolios (id, tenant_id)
    DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE scenario_runs ADD CONSTRAINT fk_scenario_snapshot_tenant
    FOREIGN KEY (base_snapshot_id, tenant_id) REFERENCES analytics_snapshots (id, tenant_id)
    DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE evidence_items ADD CONSTRAINT fk_evidence_portfolio_tenant
    FOREIGN KEY (portfolio_id, tenant_id) REFERENCES portfolios (id, tenant_id)
    DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE evidence_links ADD CONSTRAINT fk_evidence_link_item_tenant
    FOREIGN KEY (evidence_item_id, tenant_id) REFERENCES evidence_items (id, tenant_id)
    DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE agent_runs ADD CONSTRAINT fk_agent_run_portfolio_tenant
    FOREIGN KEY (portfolio_id, tenant_id) REFERENCES portfolios (id, tenant_id)
    DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE agent_run_steps ADD CONSTRAINT fk_agent_step_run_tenant
    FOREIGN KEY (agent_run_id, tenant_id) REFERENCES agent_runs (id, tenant_id)
    DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE agent_run_evidence ADD CONSTRAINT fk_agent_evidence_run_tenant
    FOREIGN KEY (agent_run_id, tenant_id) REFERENCES agent_runs (id, tenant_id)
    DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE agent_run_evidence ADD CONSTRAINT fk_agent_evidence_item_tenant
    FOREIGN KEY (evidence_item_id, tenant_id) REFERENCES evidence_items (id, tenant_id)
    DEFERRABLE INITIALLY DEFERRED;

DO $rls$
DECLARE
    table_name text;
BEGIN
    FOREACH table_name IN ARRAY ARRAY[
        'market_data_sets', 'price_observations', 'corporate_actions',
        'analytics_snapshots', 'valuation_positions', 'metric_values', 'scenario_runs',
        'evidence_items', 'evidence_links', 'agent_runs', 'agent_run_steps',
        'agent_run_evidence'
    ] LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', table_name);
        EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', table_name);
        EXECUTE format('DROP POLICY IF EXISTS tenant_isolation_%I ON %I', table_name, table_name);
        EXECUTE format(
            'CREATE POLICY tenant_isolation_%I ON %I '
            'USING (tenant_id = NULLIF(current_setting(''app.current_tenant'', true), '''')::uuid) '
            'WITH CHECK (tenant_id = NULLIF(current_setting(''app.current_tenant'', true), '''')::uuid)',
            table_name, table_name
        );
    END LOOP;
END
$rls$;

DO $immutable$
DECLARE
    table_name text;
BEGIN
    FOREACH table_name IN ARRAY ARRAY[
        'market_data_sets', 'price_observations', 'corporate_actions',
        'analytics_snapshots', 'valuation_positions', 'metric_values', 'scenario_runs',
        'evidence_items', 'evidence_links', 'agent_run_steps', 'agent_run_evidence'
    ] LOOP
        EXECUTE format('DROP TRIGGER IF EXISTS %I_append_only ON %I', table_name, table_name);
        EXECUTE format(
            'CREATE TRIGGER %I_append_only BEFORE UPDATE OR DELETE ON %I '
            'FOR EACH ROW EXECUTE FUNCTION prevent_append_only_mutation()',
            table_name, table_name
        );
    END LOOP;
END
$immutable$;

-- A run is append-only except for one atomic running-to-terminal transition. This prevents a
-- compromised runtime connection from rewriting provenance, reopening a completed run, or
-- deleting the record while still allowing durable completion.
CREATE OR REPLACE FUNCTION enforce_agent_run_transition()
RETURNS trigger
LANGUAGE plpgsql
AS $agent_transition$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'agent runs cannot be deleted';
    END IF;
    IF OLD.state <> 'running' THEN
        RAISE EXCEPTION 'terminal agent runs are immutable';
    END IF;
    IF NEW.state NOT IN ('completed', 'failed', 'timed_out') THEN
        RAISE EXCEPTION 'agent runs may only transition from running to a terminal state';
    END IF;
    IF ROW(
        NEW.id, NEW.tenant_id, NEW.portfolio_id, NEW.thread_id, NEW.initiated_by,
        NEW.request_id, NEW.question_hash, NEW.as_of, NEW.known_at, NEW.graph_version,
        NEW.prompt_bundle_version, NEW.model_route, NEW.policy_version, NEW.allowed_tools,
        NEW.checkpoint_thread_id, NEW.can_execute, NEW.started_at
    ) IS DISTINCT FROM ROW(
        OLD.id, OLD.tenant_id, OLD.portfolio_id, OLD.thread_id, OLD.initiated_by,
        OLD.request_id, OLD.question_hash, OLD.as_of, OLD.known_at, OLD.graph_version,
        OLD.prompt_bundle_version, OLD.model_route, OLD.policy_version, OLD.allowed_tools,
        OLD.checkpoint_thread_id, OLD.can_execute, OLD.started_at
    ) THEN
        RAISE EXCEPTION 'agent run identity and configuration are immutable';
    END IF;
    RETURN NEW;
END
$agent_transition$;

DROP TRIGGER IF EXISTS agent_runs_terminal_transition ON agent_runs;
CREATE TRIGGER agent_runs_terminal_transition
    BEFORE UPDATE OR DELETE ON agent_runs
    FOR EACH ROW EXECUTE FUNCTION enforce_agent_run_transition();

DROP TRIGGER IF EXISTS agent_proposals_append_only ON agent_proposals;
CREATE TRIGGER agent_proposals_append_only
    BEFORE UPDATE OR DELETE ON agent_proposals
    FOR EACH ROW EXECUTE FUNCTION prevent_append_only_mutation();

GRANT SELECT, INSERT ON market_data_sets, price_observations, corporate_actions,
    analytics_snapshots, valuation_positions, metric_values, scenario_runs,
    evidence_items, evidence_links, agent_run_steps, agent_run_evidence TO spi_runtime;
GRANT SELECT, INSERT, UPDATE ON agent_runs TO spi_runtime;
GRANT SELECT ON market_data_sets, price_observations, corporate_actions,
    analytics_snapshots, valuation_positions, metric_values, scenario_runs,
    evidence_items, evidence_links, agent_runs, agent_run_steps, agent_run_evidence
    TO spi_reporting;
REVOKE UPDATE, DELETE, TRUNCATE ON market_data_sets, price_observations, corporate_actions,
    analytics_snapshots, valuation_positions, metric_values, scenario_runs,
    evidence_items, evidence_links, agent_run_steps, agent_run_evidence FROM spi_runtime;
REVOKE DELETE, TRUNCATE ON agent_runs FROM spi_runtime;

COMMENT ON TABLE analytics_snapshots IS
    'Immutable deterministic valuation and risk roots with ledger, market-data, and methodology versions.';
COMMENT ON TABLE evidence_items IS
    'Tenant-scoped point-in-time evidence metadata and typed claims; raw licensed content stays outside logs.';
COMMENT ON COLUMN scenario_runs.can_execute IS
    'Hard invariant: a scenario is hypothetical and cannot authorize execution.';
COMMENT ON COLUMN agent_runs.checkpoint_thread_id IS
    'Tenant/portfolio-scoped key for the isolated LangGraph checkpoint schema; not an authorization token.';
COMMENT ON COLUMN agent_runs.can_execute IS
    'Hard invariant: an agent run cannot authorize ledger or broker mutation.';
