DO $roles$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'spi_runtime') THEN
        CREATE ROLE spi_runtime LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'spi_checkpoint') THEN
        CREATE ROLE spi_checkpoint LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'spi_reporting') THEN
        CREATE ROLE spi_reporting LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'spi_migration') THEN
        CREATE ROLE spi_migration LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS;
    END IF;
END
$roles$;

ALTER ROLE spi_runtime LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS;
ALTER ROLE spi_checkpoint LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS;
ALTER ROLE spi_reporting LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS;
ALTER ROLE spi_migration LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS;

DO $rds_iam$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'rds_iam') THEN
        GRANT rds_iam TO spi_runtime, spi_checkpoint, spi_reporting, spi_migration;
    END IF;
END
$rds_iam$;

DO $database_grants$
BEGIN
    EXECUTE format(
        'GRANT CONNECT ON DATABASE %I TO spi_runtime, spi_checkpoint, spi_reporting, spi_migration',
        current_database()
    );
END
$database_grants$;
GRANT USAGE ON SCHEMA public TO spi_runtime, spi_reporting;
GRANT USAGE, CREATE ON SCHEMA public TO spi_migration;
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA public TO spi_runtime;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO spi_runtime;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO spi_reporting;

REVOKE UPDATE, DELETE, TRUNCATE ON transactions FROM spi_runtime;
REVOKE UPDATE, DELETE, TRUNCATE ON ledger_versions FROM spi_runtime;
REVOKE UPDATE, DELETE, TRUNCATE ON cash_events FROM spi_runtime;
REVOKE UPDATE, DELETE, TRUNCATE ON audit_events FROM spi_runtime;
REVOKE DELETE, TRUNCATE ON outbox_events FROM spi_runtime;

ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE ON TABLES TO spi_runtime;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO spi_runtime;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT ON TABLES TO spi_reporting;

CREATE SCHEMA IF NOT EXISTS langgraph AUTHORIZATION spi_checkpoint;
REVOKE ALL ON SCHEMA langgraph FROM PUBLIC;
GRANT USAGE, CREATE ON SCHEMA langgraph TO spi_checkpoint;
ALTER ROLE spi_checkpoint SET search_path = langgraph;

DO $ownership$
DECLARE
    item record;
BEGIN
    FOR item IN
        SELECT quote_ident(schemaname) AS schema_name, quote_ident(tablename) AS object_name
        FROM pg_tables
        WHERE schemaname = 'public'
    LOOP
        EXECUTE format('ALTER TABLE %s.%s OWNER TO spi_migration', item.schema_name, item.object_name);
    END LOOP;
    FOR item IN
        SELECT quote_ident(sequence_schema) AS schema_name, quote_ident(sequence_name) AS object_name
        FROM information_schema.sequences
        WHERE sequence_schema = 'public'
    LOOP
        EXECUTE format('ALTER SEQUENCE %s.%s OWNER TO spi_migration', item.schema_name, item.object_name);
    END LOOP;
END
$ownership$;
