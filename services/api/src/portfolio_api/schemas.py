from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

PortfolioType = Literal["self_managed", "pms", "model", "interest"]
SourceRole = Literal[
    "brokerage_ledger",
    "broker_statement",
    "pms_statement",
    "research",
    "manual",
]


class PortfolioCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    portfolio_type: PortfolioType
    base_currency: str = Field(default="INR", pattern=r"^[A-Z]{3}$")
    benchmark_code: str = Field(min_length=2, max_length=64)
    valuation_timezone: str = "Asia/Kolkata"


class PortfolioRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    portfolio_type: str
    base_currency: str
    benchmark_code: str
    valuation_timezone: str
    status: str
    version: int
    ledger_version: int
    rules: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class UploadRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    portfolio_id: UUID
    original_name: str
    declared_type: str | None
    detected_type: str
    source_role: str
    authority_level: str
    size_bytes: int
    sha256: str
    state: str
    version: int
    parser_summary: dict[str, Any]
    error_code: str | None
    created_at: datetime
    updated_at: datetime


class AnalyticsSnapshot(BaseModel):
    portfolio_id: UUID
    quality_state: Literal["trusted", "needs_review", "partial", "stale"]
    as_of: datetime
    base_currency: str
    ledger_version: int
    metrics: dict[str, str | None]
    rules: dict[str, Any]
    limitations: list[str]


LedgerEventType = Literal[
    "buy",
    "sell",
    "cash_deposit",
    "cash_withdrawal",
    "dividend",
    "dividend_cash",
    "fee",
    "price_mark",
    "transfer_in",
    "transfer_out",
    "reversal",
]


class LedgerEventCreate(BaseModel):
    event_type: LedgerEventType
    trade_date: datetime
    instrument_reference: str | None = Field(default=None, min_length=1, max_length=128)
    quantity: Decimal | None = Field(default=None, decimal_places=10)
    price: Decimal | None = Field(default=None, decimal_places=10)
    gross_amount: Decimal = Field(ge=0, decimal_places=8)
    currency: str = Field(default="INR", pattern=r"^[A-Z]{3}$")
    source_reference: str = Field(min_length=1, max_length=255)
    confirm_publication: bool = False

    @model_validator(mode="after")
    def validate_event_shape(self) -> LedgerEventCreate:
        if not self.confirm_publication:
            raise ValueError("confirm_publication must be true for an append-only ledger event")
        security_events = {"buy", "sell"}
        if self.event_type in security_events:
            if not self.instrument_reference or self.quantity is None or self.price is None:
                raise ValueError(
                    "buy and sell events require instrument_reference, quantity, and price"
                )
            if self.quantity <= 0 or self.price <= 0 or self.gross_amount <= 0:
                raise ValueError("buy and sell quantity, price, and gross_amount must be positive")
        elif self.event_type == "price_mark":
            if not self.instrument_reference or self.price is None or self.price <= 0:
                raise ValueError(
                    "price_mark events require an instrument_reference and positive price"
                )
            if self.quantity is not None or self.gross_amount != 0:
                raise ValueError("price_mark quantity must be empty and gross_amount must be zero")
        elif self.quantity is not None or self.price is not None:
            raise ValueError("cash, dividend, and fee events cannot include quantity or price")
        return self


class LedgerEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    portfolio_id: UUID
    event_type: str
    trade_date: datetime
    instrument_reference: str | None
    quantity: Decimal | None
    price: Decimal | None
    gross_amount: Decimal
    currency: str
    source_reference: str
    recorded_at: datetime


class HoldingRead(BaseModel):
    instrument_reference: str
    quantity: str
    average_cost: str
    last_price: str | None
    market_value: str | None
    cost_basis: str
    unrealized_pnl: str | None
    weight_percent: str | None
    price_as_of: datetime | None


class LedgerSnapshot(BaseModel):
    portfolio_id: UUID
    as_of: datetime
    ledger_version: int
    cash_balance: str
    available_cash: str
    protected_cash: str
    net_invested_capital: str
    securities_market_value: str
    total_value: str
    realized_pnl: str
    holdings: list[HoldingRead]
    limitations: list[str]


class MonitorAlert(BaseModel):
    id: str
    severity: Literal["info", "warning", "critical"]
    kind: str
    title: str
    detail: str
    instrument_reference: str | None = None
    observed_value: str | None = None
    threshold_value: str | None = None
    evidence_ids: list[str] = Field(default_factory=list)


class MonitorSnapshot(BaseModel):
    portfolio_id: UUID
    as_of: datetime
    state: Literal["clear", "attention", "blocked"]
    alerts: list[MonitorAlert]
    checked_rules: list[str]
    limitations: list[str]


class ErrorBody(BaseModel):
    code: str
    message: str
    retryable: bool = False
    trace_id: str | None = None


class UploadInitiate(BaseModel):
    portfolio_id: UUID
    original_name: str = Field(min_length=1, max_length=255)
    source_role: SourceRole = "brokerage_ledger"
    content_type: Literal["text/csv"] = "text/csv"
    size_bytes: int = Field(gt=0, le=52_428_800)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class UploadInitiated(BaseModel):
    upload_id: UUID
    state: Literal["initiated"]
    upload_url: str
    method: Literal["POST", "PUT"]
    fields: dict[str, str] = Field(default_factory=dict)
    required_headers: dict[str, str] = Field(default_factory=dict)
    expires_at: datetime
    version: int


class JobAccepted(BaseModel):
    job_id: UUID
    state: str
    resource_type: str
    resource_id: UUID


class JobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    job_type: str
    state: str
    resource_type: str
    resource_id: UUID
    attempts: int
    result: dict[str, Any]
    error_code: str | None
    trace_id: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


class DocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    portfolio_id: UUID
    upload_id: UUID
    document_family: str
    state: str
    source_hash: str
    created_at: datetime
    updated_at: datetime


class ExtractionRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    document_id: UUID
    parser_name: str
    parser_version: str
    template_id: str
    state: str
    started_at: datetime
    completed_at: datetime | None
    metrics_json: dict[str, Any]


class ExtractedRecordRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    extraction_run_id: UUID
    source_row: int
    raw_hash: str
    normalized_data: dict[str, Any]
    confidence: Decimal
    state: str
    version: int
    edited_by: UUID | None
    edited_at: datetime | None


class ExtractedRecordPatch(BaseModel):
    normalized_data: dict[str, Any]


class ReconciliationResolution(BaseModel):
    resolution: Literal["accept", "exclude", "replace"]
    reason: str = Field(min_length=4, max_length=500)
    replacement_data: dict[str, Any] | None = None


class ReconciliationCaseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    portfolio_id: UUID
    extracted_record_id: UUID | None
    kind: str
    severity: str
    state: str
    details: dict[str, Any]
    resolution: dict[str, Any]
    resolved_by: UUID | None
    resolved_at: datetime | None
    created_at: datetime


class ImportBatchRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    portfolio_id: UUID
    document_id: UUID
    extraction_run_id: UUID
    state: str
    version: int
    base_ledger_version: int
    content_hash: str
    validated_hash: str | None
    validation_summary: dict[str, Any]
    published_ledger_version: int | None
    created_by: UUID
    approved_by: UUID | None
    published_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ImportBatchValidate(BaseModel):
    included_record_ids: list[UUID] = Field(min_length=1)
    excluded_records: dict[UUID, str] = Field(default_factory=dict)


class ImportBatchPublish(BaseModel):
    included_record_ids: list[UUID] = Field(min_length=1)
    excluded_records: dict[UUID, str] = Field(default_factory=dict)
    validated_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    acknowledgment: Literal["I reviewed this batch and authorize immutable ledger publication."]


class LedgerVersionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    portfolio_id: UUID
    version: int
    import_batch_id: UUID | None
    event_count: int
    content_hash: str
    published_by: UUID
    published_at: datetime


class PublicationAccepted(BaseModel):
    job_id: UUID
    import_batch_id: UUID
    ledger_version: int
    state: Literal["completed"]
    audit_event_id: UUID
