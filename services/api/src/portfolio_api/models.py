from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import JSON


def utc_now() -> datetime:
    return datetime.now(UTC)


def new_uuid() -> UUID:
    return uuid4()


JSON_TYPE = JSON().with_variant(JSONB(), "postgresql")


class Base(DeclarativeBase):
    pass


class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_uuid)
    name: Mapped[str] = mapped_column(String(160))
    tenant_type: Mapped[str] = mapped_column(String(32), default="individual")
    base_currency: Mapped[str] = mapped_column(String(3), default="INR")
    status: Mapped[str] = mapped_column(String(24), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class User(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_uuid)
    identity_provider_subject: Mapped[str] = mapped_column(String(255), unique=True)
    email_ciphertext: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(24), default="active")
    locale: Mapped[str] = mapped_column(String(16), default="en-IN")
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Kolkata")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class TenantMembership(Base):
    __tablename__ = "tenant_memberships"
    __table_args__ = (
        UniqueConstraint("tenant_id", "user_id", name="uq_membership_tenant_user"),
        Index("ix_membership_user_status", "user_id", "status"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_uuid)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    role: Mapped[str] = mapped_column(String(24), default="viewer")
    status: Mapped[str] = mapped_column(String(24), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class Portfolio(Base):
    __tablename__ = "portfolios"
    __table_args__ = (
        Index("ix_portfolios_tenant_created", "tenant_id", "created_at"),
        UniqueConstraint("tenant_id", "name", name="uq_portfolio_tenant_name"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_uuid)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    owner_user_id: Mapped[UUID] = mapped_column(nullable=False)
    name: Mapped[str] = mapped_column(String(160))
    portfolio_type: Mapped[str] = mapped_column(String(32))
    base_currency: Mapped[str] = mapped_column(String(3), default="INR")
    benchmark_code: Mapped[str] = mapped_column(String(64))
    valuation_timezone: Mapped[str] = mapped_column(String(64), default="Asia/Kolkata")
    status: Mapped[str] = mapped_column(String(24), default="active")
    version: Mapped[int] = mapped_column(default=1)
    ledger_version: Mapped[int] = mapped_column(default=0)
    rules: Mapped[dict[str, Any]] = mapped_column(
        JSON_TYPE,
        default=lambda: {
            "equal_weighting_allowed": False,
            "protected_cash": {"amount": "2500000.00", "currency": "INR"},
            "max_position_weight_percent": "25.00",
            "review_cadence": "weekly",
        },
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class Upload(Base):
    __tablename__ = "uploads"
    __table_args__ = (
        Index("ix_uploads_tenant_portfolio_created", "tenant_id", "portfolio_id", "created_at"),
        UniqueConstraint(
            "tenant_id",
            "portfolio_id",
            "sha256",
            "source_role",
            name="uq_upload_content_authority",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_uuid)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    portfolio_id: Mapped[UUID] = mapped_column(ForeignKey("portfolios.id"), nullable=False)
    created_by: Mapped[UUID] = mapped_column(nullable=False)
    object_key: Mapped[str] = mapped_column(String(512))
    original_name: Mapped[str] = mapped_column(String(255))
    declared_type: Mapped[str | None] = mapped_column(String(160), nullable=True)
    detected_type: Mapped[str] = mapped_column(String(64))
    source_role: Mapped[str] = mapped_column(String(40))
    authority_level: Mapped[str] = mapped_column(String(24))
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    sha256: Mapped[str] = mapped_column(String(64))
    state: Mapped[str] = mapped_column(String(32))
    version: Mapped[int] = mapped_column(default=1)
    parser_summary: Mapped[dict[str, Any]] = mapped_column(JSON_TYPE, default=dict)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class Transaction(Base):
    __tablename__ = "transactions"
    __table_args__ = (
        Index("ix_transactions_tenant_portfolio_date", "tenant_id", "portfolio_id", "trade_date"),
        UniqueConstraint(
            "tenant_id",
            "portfolio_id",
            "source_reference",
            name="uq_transaction_source_reference",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_uuid)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    portfolio_id: Mapped[UUID] = mapped_column(ForeignKey("portfolios.id"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(32))
    trade_date: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    instrument_reference: Mapped[str | None] = mapped_column(String(128), nullable=True)
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(28, 10), nullable=True)
    price: Mapped[Decimal | None] = mapped_column(Numeric(28, 10), nullable=True)
    gross_amount: Mapped[Decimal] = mapped_column(Numeric(28, 8))
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    source_reference: Mapped[str] = mapped_column(String(255))
    account_id: Mapped[UUID | None] = mapped_column(ForeignKey("accounts.id"), nullable=True)
    instrument_id: Mapped[UUID | None] = mapped_column(ForeignKey("instruments.id"), nullable=True)
    import_batch_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("import_batches.id"), nullable=True
    )
    ledger_version: Mapped[int] = mapped_column(default=0)
    fees: Mapped[Decimal] = mapped_column(Numeric(28, 8), default=Decimal("0"))
    taxes: Mapped[Decimal] = mapped_column(Numeric(28, 8), default=Decimal("0"))
    cash_delta: Mapped[Decimal | None] = mapped_column(Numeric(28, 8), nullable=True)
    reversal_of_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("transactions.id"), nullable=True
    )
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class Account(Base):
    __tablename__ = "accounts"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "portfolio_id",
            "provider",
            "masked_reference",
            name="uq_account_provider_reference",
        ),
        Index("ix_accounts_tenant_portfolio", "tenant_id", "portfolio_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_uuid)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    portfolio_id: Mapped[UUID] = mapped_column(ForeignKey("portfolios.id"), nullable=False)
    provider: Mapped[str] = mapped_column(String(40), default="generic_csv")
    account_type: Mapped[str] = mapped_column(String(32), default="brokerage")
    masked_reference: Mapped[str] = mapped_column(String(160))
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    status: Mapped[str] = mapped_column(String(24), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class Instrument(Base):
    __tablename__ = "instruments"
    __table_args__ = (
        UniqueConstraint("identifier_type", "identifier", name="uq_instrument_identifier"),
        Index("ix_instruments_exchange_symbol", "exchange", "symbol"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_uuid)
    identifier_type: Mapped[str] = mapped_column(String(24))
    identifier: Mapped[str] = mapped_column(String(128))
    exchange: Mapped[str] = mapped_column(String(16))
    symbol: Mapped[str] = mapped_column(String(64))
    asset_type: Mapped[str] = mapped_column(String(32), default="equity")
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    status: Mapped[str] = mapped_column(String(24), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class InstrumentAlias(Base):
    __tablename__ = "instrument_aliases"
    __table_args__ = (UniqueConstraint("provider", "alias", name="uq_instrument_alias_provider"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_uuid)
    instrument_id: Mapped[UUID] = mapped_column(ForeignKey("instruments.id"), nullable=False)
    provider: Mapped[str] = mapped_column(String(40))
    alias: Mapped[str] = mapped_column(String(128))
    verification_status: Mapped[str] = mapped_column(String(24), default="verified")
    valid_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    valid_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (Index("ix_documents_tenant_portfolio", "tenant_id", "portfolio_id"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_uuid)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    portfolio_id: Mapped[UUID] = mapped_column(ForeignKey("portfolios.id"), nullable=False)
    upload_id: Mapped[UUID] = mapped_column(ForeignKey("uploads.id"), unique=True)
    document_family: Mapped[str] = mapped_column(String(40), default="generic_ledger_csv")
    state: Mapped[str] = mapped_column(String(32), default="quarantined")
    source_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class ExtractionRun(Base):
    __tablename__ = "extraction_runs"
    __table_args__ = (Index("ix_extraction_document_started", "document_id", "started_at"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_uuid)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    document_id: Mapped[UUID] = mapped_column(ForeignKey("documents.id"), nullable=False)
    parser_name: Mapped[str] = mapped_column(String(80))
    parser_version: Mapped[str] = mapped_column(String(32))
    template_id: Mapped[str] = mapped_column(String(80))
    state: Mapped[str] = mapped_column(String(32), default="running")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    metrics_json: Mapped[dict[str, Any]] = mapped_column(JSON_TYPE, default=dict)


class ExtractedRecord(Base):
    __tablename__ = "extracted_records"
    __table_args__ = (
        UniqueConstraint("extraction_run_id", "source_row", name="uq_extraction_source_row"),
        Index("ix_extracted_tenant_run", "tenant_id", "extraction_run_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_uuid)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    extraction_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("extraction_runs.id"), nullable=False
    )
    source_row: Mapped[int] = mapped_column(Integer)
    raw_hash: Mapped[str] = mapped_column(String(64))
    normalized_data: Mapped[dict[str, Any]] = mapped_column(JSON_TYPE)
    confidence: Mapped[Decimal] = mapped_column(Numeric(5, 4), default=Decimal("1"))
    state: Mapped[str] = mapped_column(String(24), default="candidate")
    version: Mapped[int] = mapped_column(default=1)
    edited_by: Mapped[UUID | None] = mapped_column(nullable=True)
    edited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class MappingRule(Base):
    __tablename__ = "mapping_rules"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "provider",
            "document_family",
            "source_field",
            name="uq_mapping_rule_scope",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_uuid)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    provider: Mapped[str] = mapped_column(String(40), default="generic_csv")
    document_family: Mapped[str] = mapped_column(String(40))
    source_field: Mapped[str] = mapped_column(String(80))
    target_field: Mapped[str | None] = mapped_column(String(80), nullable=True)
    transform_version: Mapped[str] = mapped_column(String(32), default="1")
    status: Mapped[str] = mapped_column(String(24), default="active")
    exclusion_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)


class ReconciliationCase(Base):
    __tablename__ = "reconciliation_cases"
    __table_args__ = (Index("ix_reconciliation_tenant_state", "tenant_id", "state"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_uuid)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    portfolio_id: Mapped[UUID] = mapped_column(ForeignKey("portfolios.id"), nullable=False)
    import_batch_id: Mapped[UUID] = mapped_column(ForeignKey("import_batches.id"), nullable=False)
    extracted_record_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("extracted_records.id"), nullable=True
    )
    kind: Mapped[str] = mapped_column(String(48))
    severity: Mapped[str] = mapped_column(String(16), default="error")
    state: Mapped[str] = mapped_column(String(24), default="open")
    details: Mapped[dict[str, Any]] = mapped_column(JSON_TYPE, default=dict)
    resolution: Mapped[dict[str, Any]] = mapped_column(JSON_TYPE, default=dict)
    resolved_by: Mapped[UUID | None] = mapped_column(nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class ImportBatch(Base):
    __tablename__ = "import_batches"
    __table_args__ = (
        UniqueConstraint("tenant_id", "content_hash", name="uq_import_batch_content"),
        Index("ix_import_batch_tenant_portfolio", "tenant_id", "portfolio_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_uuid)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    portfolio_id: Mapped[UUID] = mapped_column(ForeignKey("portfolios.id"), nullable=False)
    document_id: Mapped[UUID] = mapped_column(ForeignKey("documents.id"), nullable=False)
    extraction_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("extraction_runs.id"), nullable=False
    )
    state: Mapped[str] = mapped_column(String(32), default="draft")
    version: Mapped[int] = mapped_column(default=1)
    base_ledger_version: Mapped[int] = mapped_column(default=0)
    content_hash: Mapped[str] = mapped_column(String(64))
    validated_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    validation_summary: Mapped[dict[str, Any]] = mapped_column(JSON_TYPE, default=dict)
    published_ledger_version: Mapped[int | None] = mapped_column(nullable=True)
    created_by: Mapped[UUID] = mapped_column(nullable=False)
    approved_by: Mapped[UUID | None] = mapped_column(nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class ImportBatchRecord(Base):
    __tablename__ = "import_batch_records"
    __table_args__ = (
        UniqueConstraint("import_batch_id", "extracted_record_id", name="uq_batch_record"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_uuid)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    import_batch_id: Mapped[UUID] = mapped_column(ForeignKey("import_batches.id"), nullable=False)
    extracted_record_id: Mapped[UUID] = mapped_column(
        ForeignKey("extracted_records.id"), nullable=False
    )
    disposition: Mapped[str] = mapped_column(String(24), default="pending")
    exclusion_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)


class LedgerVersion(Base):
    __tablename__ = "ledger_versions"
    __table_args__ = (
        UniqueConstraint("tenant_id", "portfolio_id", "version", name="uq_ledger_version"),
        Index("ix_ledger_versions_portfolio", "tenant_id", "portfolio_id", "version"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_uuid)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    portfolio_id: Mapped[UUID] = mapped_column(ForeignKey("portfolios.id"), nullable=False)
    version: Mapped[int] = mapped_column(Integer)
    import_batch_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("import_batches.id"), nullable=True
    )
    event_count: Mapped[int] = mapped_column(Integer)
    content_hash: Mapped[str] = mapped_column(String(64))
    published_by: Mapped[UUID] = mapped_column(nullable=False)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class CashEvent(Base):
    __tablename__ = "cash_events"
    __table_args__ = (
        Index("ix_cash_events_portfolio_date", "tenant_id", "portfolio_id", "event_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_uuid)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    portfolio_id: Mapped[UUID] = mapped_column(ForeignKey("portfolios.id"), nullable=False)
    transaction_id: Mapped[UUID] = mapped_column(ForeignKey("transactions.id"), nullable=False)
    import_batch_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("import_batches.id"), nullable=True
    )
    event_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    amount: Mapped[Decimal] = mapped_column(Numeric(28, 8))
    currency: Mapped[str] = mapped_column(String(3))
    event_type: Mapped[str] = mapped_column(String(32))
    ledger_version: Mapped[int] = mapped_column(Integer)


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (Index("ix_jobs_tenant_state", "tenant_id", "state"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_uuid)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    job_type: Mapped[str] = mapped_column(String(48))
    state: Mapped[str] = mapped_column(String(24), default="queued")
    resource_type: Mapped[str] = mapped_column(String(48))
    resource_id: Mapped[UUID] = mapped_column(nullable=False)
    attempts: Mapped[int] = mapped_column(default=0)
    result: Mapped[dict[str, Any]] = mapped_column(JSON_TYPE, default=dict)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    trace_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class IdempotencyRecord(Base):
    __tablename__ = "idempotency_records"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "principal_id",
            "endpoint",
            "idempotency_key",
            name="uq_idempotency_scope",
        ),
        Index("ix_idempotency_expires", "expires_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_uuid)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    principal_id: Mapped[UUID] = mapped_column(nullable=False)
    endpoint: Mapped[str] = mapped_column(String(160))
    idempotency_key: Mapped[str] = mapped_column(String(160))
    request_hash: Mapped[str] = mapped_column(String(64))
    status_code: Mapped[int] = mapped_column(Integer)
    response_body: Mapped[dict[str, Any]] = mapped_column(JSON_TYPE, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class OutboxEvent(Base):
    __tablename__ = "outbox_events"
    __table_args__ = (
        UniqueConstraint("event_id", name="uq_outbox_event_id"),
        Index("ix_outbox_pending", "published_at", "occurred_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_uuid)
    event_id: Mapped[UUID] = mapped_column(default=new_uuid)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(96))
    event_version: Mapped[int] = mapped_column(default=1)
    aggregate_type: Mapped[str] = mapped_column(String(48))
    aggregate_id: Mapped[UUID] = mapped_column(nullable=False)
    aggregate_version: Mapped[int] = mapped_column(Integer)
    trace_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON_TYPE, default=dict)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class MarketDataSet(Base):
    """Immutable, tenant-scoped manifest for licensed point-in-time market inputs."""

    __tablename__ = "market_data_sets"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "portfolio_id",
            "provider",
            "provider_version",
            name="uq_market_data_set_version",
        ),
        Index("ix_market_data_sets_cutoff", "tenant_id", "portfolio_id", "cutoff_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_uuid)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    portfolio_id: Mapped[UUID] = mapped_column(ForeignKey("portfolios.id"), nullable=False)
    provider: Mapped[str] = mapped_column(String(80))
    provider_version: Mapped[str] = mapped_column(String(80))
    rights_basis: Mapped[str] = mapped_column(String(24))
    cutoff_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    known_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    content_hash: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(24), default="sealed")
    created_by: Mapped[UUID] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class PriceObservation(Base):
    __tablename__ = "price_observations"
    __table_args__ = (
        CheckConstraint("known_at >= observed_at", name="ck_price_time"),
        UniqueConstraint(
            "market_data_set_id",
            "instrument_reference",
            "observed_at",
            name="uq_price_observation",
        ),
        Index(
            "ix_price_observations_lookup",
            "tenant_id",
            "market_data_set_id",
            "instrument_reference",
            "observed_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_uuid)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    market_data_set_id: Mapped[UUID] = mapped_column(
        ForeignKey("market_data_sets.id"), nullable=False
    )
    instrument_reference: Mapped[str] = mapped_column(String(128))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    known_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    close_price: Mapped[Decimal] = mapped_column(Numeric(28, 10))
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    quality: Mapped[str] = mapped_column(String(24), default="verified")
    source_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class CorporateAction(Base):
    __tablename__ = "corporate_actions"
    __table_args__ = (
        UniqueConstraint(
            "market_data_set_id",
            "instrument_reference",
            "action_type",
            "effective_at",
            name="uq_corporate_action",
        ),
        Index(
            "ix_corporate_actions_lookup",
            "tenant_id",
            "market_data_set_id",
            "instrument_reference",
            "effective_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_uuid)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    market_data_set_id: Mapped[UUID] = mapped_column(
        ForeignKey("market_data_sets.id"), nullable=False
    )
    instrument_reference: Mapped[str] = mapped_column(String(128))
    action_type: Mapped[str] = mapped_column(String(32))
    effective_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    known_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    split_factor: Mapped[Decimal | None] = mapped_column(Numeric(28, 12), nullable=True)
    cash_amount_per_unit: Mapped[Decimal | None] = mapped_column(Numeric(28, 10), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    source_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class AnalyticsSnapshotRecord(Base):
    __tablename__ = "analytics_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "portfolio_id",
            "input_hash",
            name="uq_analytics_snapshot_inputs",
        ),
        Index(
            "ix_analytics_snapshots_latest",
            "tenant_id",
            "portfolio_id",
            "as_of",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_uuid)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    portfolio_id: Mapped[UUID] = mapped_column(ForeignKey("portfolios.id"), nullable=False)
    market_data_set_id: Mapped[UUID] = mapped_column(
        ForeignKey("market_data_sets.id"), nullable=False
    )
    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    known_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ledger_version: Mapped[int] = mapped_column(Integer)
    market_data_version: Mapped[str] = mapped_column(String(80))
    methodology_version: Mapped[str] = mapped_column(String(40))
    benchmark_code: Mapped[str] = mapped_column(String(64))
    base_currency: Mapped[str] = mapped_column(String(3))
    input_hash: Mapped[str] = mapped_column(String(64))
    quality_state: Mapped[str] = mapped_column(String(24))
    limitations: Mapped[list[str]] = mapped_column(JSON_TYPE, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class ValuationPosition(Base):
    __tablename__ = "valuation_positions"
    __table_args__ = (
        UniqueConstraint(
            "analytics_snapshot_id",
            "instrument_reference",
            name="uq_valuation_position",
        ),
        Index("ix_valuation_positions_snapshot", "tenant_id", "analytics_snapshot_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_uuid)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    analytics_snapshot_id: Mapped[UUID] = mapped_column(
        ForeignKey("analytics_snapshots.id"), nullable=False
    )
    instrument_reference: Mapped[str] = mapped_column(String(128))
    quantity: Mapped[Decimal] = mapped_column(Numeric(28, 10))
    cost_basis: Mapped[Decimal] = mapped_column(Numeric(28, 8))
    price: Mapped[Decimal | None] = mapped_column(Numeric(28, 10), nullable=True)
    price_as_of: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    market_value: Mapped[Decimal | None] = mapped_column(Numeric(28, 8), nullable=True)
    weight: Mapped[Decimal | None] = mapped_column(Numeric(20, 12), nullable=True)
    status: Mapped[str] = mapped_column(String(24), default="valued")


class MetricValue(Base):
    __tablename__ = "metric_values"
    __table_args__ = (
        UniqueConstraint(
            "analytics_snapshot_id",
            "metric_code",
            "dimension_type",
            "dimension_id",
            name="uq_metric_value_dimension",
        ),
        Index("ix_metric_values_snapshot", "tenant_id", "analytics_snapshot_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_uuid)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    analytics_snapshot_id: Mapped[UUID] = mapped_column(
        ForeignKey("analytics_snapshots.id"), nullable=False
    )
    metric_code: Mapped[str] = mapped_column(String(64))
    dimension_type: Mapped[str] = mapped_column(String(32), default="portfolio")
    dimension_id: Mapped[str] = mapped_column(String(128), default="portfolio")
    value: Mapped[Decimal | None] = mapped_column(Numeric(28, 12), nullable=True)
    unit: Mapped[str] = mapped_column(String(24))
    status: Mapped[str] = mapped_column(String(24), default="available")
    details: Mapped[dict[str, Any]] = mapped_column(JSON_TYPE, default=dict)


class ScenarioRun(Base):
    __tablename__ = "scenario_runs"
    __table_args__ = (
        CheckConstraint("can_execute = false", name="ck_scenario_never_executes"),
        Index("ix_scenario_runs_portfolio", "tenant_id", "portfolio_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_uuid)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    portfolio_id: Mapped[UUID] = mapped_column(ForeignKey("portfolios.id"), nullable=False)
    created_by: Mapped[UUID] = mapped_column(nullable=False)
    base_snapshot_id: Mapped[UUID] = mapped_column(
        ForeignKey("analytics_snapshots.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(160))
    status: Mapped[str] = mapped_column(String(24), default="completed")
    assumptions: Mapped[dict[str, Any]] = mapped_column(JSON_TYPE, default=dict)
    results: Mapped[dict[str, Any]] = mapped_column(JSON_TYPE, default=dict)
    constraint_results: Mapped[list[dict[str, Any]]] = mapped_column(JSON_TYPE, default=list)
    engine_version: Mapped[str] = mapped_column(String(40))
    can_execute: Mapped[bool] = mapped_column(Boolean, default=False)
    input_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class EvidenceItem(Base):
    __tablename__ = "evidence_items"
    __table_args__ = (
        UniqueConstraint("tenant_id", "portfolio_id", "content_hash", name="uq_evidence_hash"),
        Index("ix_evidence_cutoff", "tenant_id", "portfolio_id", "known_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_uuid)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    portfolio_id: Mapped[UUID] = mapped_column(ForeignKey("portfolios.id"), nullable=False)
    source_type: Mapped[str] = mapped_column(String(40))
    title: Mapped[str] = mapped_column(String(255))
    publisher: Mapped[str] = mapped_column(String(160))
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    known_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    content_hash: Mapped[str] = mapped_column(String(64))
    locator: Mapped[dict[str, Any]] = mapped_column(JSON_TYPE, default=dict)
    claims: Mapped[list[dict[str, Any]]] = mapped_column(JSON_TYPE, default=list)
    quality: Mapped[str] = mapped_column(String(24), default="pending")
    rights_basis: Mapped[str] = mapped_column(String(24))
    cutoff_eligible: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by: Mapped[UUID] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class EvidenceLink(Base):
    __tablename__ = "evidence_links"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "from_type",
            "from_id",
            "evidence_item_id",
            "claim_key",
            name="uq_evidence_link",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_uuid)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    from_type: Mapped[str] = mapped_column(String(40))
    from_id: Mapped[UUID] = mapped_column(nullable=False)
    evidence_item_id: Mapped[UUID] = mapped_column(ForeignKey("evidence_items.id"), nullable=False)
    relation: Mapped[str] = mapped_column(String(24), default="supports")
    claim_key: Mapped[str] = mapped_column(String(128))


class AgentRunRecord(Base):
    __tablename__ = "agent_runs"
    __table_args__ = (
        CheckConstraint("can_execute = false", name="ck_agent_run_never_executes"),
        CheckConstraint(
            "state IN ('running', 'completed', 'failed', 'timed_out')",
            name="ck_agent_run_state",
        ),
        CheckConstraint(
            "completed_at IS NULL OR completed_at >= started_at",
            name="ck_agent_run_completed_time",
        ),
        CheckConstraint(
            """
            (state = 'running' AND completed_at IS NULL AND result_hash IS NULL
                AND error_code IS NULL)
            OR
            (state = 'completed' AND completed_at IS NOT NULL AND result_hash IS NOT NULL
                AND error_code IS NULL)
            OR
            (state IN ('failed', 'timed_out') AND completed_at IS NOT NULL
                AND result_hash IS NULL AND error_code IS NOT NULL)
            """,
            name="ck_agent_run_completion_shape",
        ),
        UniqueConstraint("tenant_id", "request_id", name="uq_agent_run_request"),
        Index("ix_agent_runs_portfolio", "tenant_id", "portfolio_id", "started_at"),
        Index("ix_agent_runs_thread", "tenant_id", "thread_id", "started_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_uuid)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    portfolio_id: Mapped[UUID] = mapped_column(ForeignKey("portfolios.id"), nullable=False)
    thread_id: Mapped[UUID] = mapped_column(nullable=False)
    initiated_by: Mapped[UUID] = mapped_column(nullable=False)
    request_id: Mapped[str] = mapped_column(String(96))
    question_hash: Mapped[str] = mapped_column(String(64))
    intent: Mapped[str | None] = mapped_column(String(40), nullable=True)
    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    known_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    graph_version: Mapped[str] = mapped_column(String(64))
    prompt_bundle_version: Mapped[str] = mapped_column(String(64))
    model_route: Mapped[str] = mapped_column(String(80))
    policy_version: Mapped[str] = mapped_column(String(64))
    allowed_tools: Mapped[list[str]] = mapped_column(JSON_TYPE, default=list)
    checkpoint_thread_id: Mapped[str] = mapped_column(String(255))
    state: Mapped[str] = mapped_column(String(24), default="running")
    stages: Mapped[list[str]] = mapped_column(JSON_TYPE, default=list)
    citations: Mapped[list[dict[str, Any]]] = mapped_column(JSON_TYPE, default=list)
    policy: Mapped[dict[str, Any]] = mapped_column(JSON_TYPE, default=dict)
    result_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    can_execute: Mapped[bool] = mapped_column(Boolean, default=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AgentRunStep(Base):
    __tablename__ = "agent_run_steps"
    __table_args__ = (
        CheckConstraint(
            "state IN ('completed', 'failed', 'timed_out')",
            name="ck_agent_step_state",
        ),
        UniqueConstraint("agent_run_id", "node_name", "attempt", name="uq_agent_run_step"),
        Index("ix_agent_run_steps_run", "tenant_id", "agent_run_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_uuid)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    agent_run_id: Mapped[UUID] = mapped_column(ForeignKey("agent_runs.id"), nullable=False)
    node_name: Mapped[str] = mapped_column(String(80))
    attempt: Mapped[int] = mapped_column(Integer, default=1)
    state: Mapped[str] = mapped_column(String(24), default="completed")
    public_summary: Mapped[str] = mapped_column(String(255))
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class AgentRunEvidence(Base):
    __tablename__ = "agent_run_evidence"
    __table_args__ = (
        CheckConstraint(
            "relation IN ('supports', 'contradicts', 'contextualizes')",
            name="ck_agent_run_evidence_relation",
        ),
        UniqueConstraint(
            "agent_run_id", "evidence_item_id", "claim_key", name="uq_agent_run_evidence"
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_uuid)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    agent_run_id: Mapped[UUID] = mapped_column(ForeignKey("agent_runs.id"), nullable=False)
    evidence_item_id: Mapped[UUID] = mapped_column(ForeignKey("evidence_items.id"), nullable=False)
    claim_key: Mapped[str] = mapped_column(String(128))
    relation: Mapped[str] = mapped_column(String(24), default="supports")


class AgentProposalRecord(Base):
    __tablename__ = "agent_proposals"
    __table_args__ = (
        CheckConstraint("can_execute = false", name="ck_agent_proposal_never_executes"),
        Index("ix_agent_proposals_tenant_portfolio", "tenant_id", "portfolio_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_uuid)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    portfolio_id: Mapped[UUID] = mapped_column(ForeignKey("portfolios.id"), nullable=False)
    run_id: Mapped[UUID] = mapped_column(nullable=False)
    proposal: Mapped[dict[str, Any]] = mapped_column(JSON_TYPE, default=dict)
    can_execute: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class AuditEvent(Base):
    __tablename__ = "audit_events"
    __table_args__ = (Index("ix_audit_tenant_occurred", "tenant_id", "occurred_at"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_uuid)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    actor_id: Mapped[UUID | None] = mapped_column(nullable=True)
    action: Mapped[str] = mapped_column(String(96))
    resource_type: Mapped[str] = mapped_column(String(64))
    resource_id: Mapped[UUID | None] = mapped_column(nullable=True)
    trace_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    details: Mapped[dict[str, Any]] = mapped_column(JSON_TYPE, default=dict)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
