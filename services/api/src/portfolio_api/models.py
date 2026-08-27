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
