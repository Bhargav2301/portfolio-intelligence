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


def _require_timezone(*values: datetime) -> None:
    if any(value.tzinfo is None or value.utcoffset() is None for value in values):
        raise ValueError("all timestamps must include a UTC offset")


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
    snapshot_id: UUID | None = None
    portfolio_id: UUID
    quality_state: Literal["trusted", "needs_review", "partial", "stale"]
    as_of: datetime
    known_at: datetime | None = None
    base_currency: str
    ledger_version: int
    market_data_version: str | None = None
    methodology_version: str | None = None
    input_hash: str | None = None
    metrics: dict[str, str | None]
    rules: dict[str, Any]
    limitations: list[str]


RightsBasis = Literal["licensed", "user_provided", "internal"]


class PriceObservationCreate(BaseModel):
    instrument_reference: str = Field(min_length=1, max_length=128)
    observed_at: datetime
    known_at: datetime
    close_price: Decimal = Field(gt=0, decimal_places=10)
    currency: str = Field(default="INR", pattern=r"^[A-Z]{3}$")
    quality: Literal["verified", "estimated"] = "verified"
    source_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_observation_time(self) -> PriceObservationCreate:
        _require_timezone(self.observed_at, self.known_at)
        if self.known_at < self.observed_at:
            raise ValueError("price known_at cannot be earlier than observed_at")
        return self


class CorporateActionCreate(BaseModel):
    instrument_reference: str = Field(min_length=1, max_length=128)
    action_type: Literal["split", "cash_dividend"]
    effective_at: datetime
    known_at: datetime
    split_factor: Decimal | None = Field(default=None, gt=0, decimal_places=12)
    cash_amount_per_unit: Decimal | None = Field(default=None, ge=0, decimal_places=10)
    currency: str = Field(default="INR", pattern=r"^[A-Z]{3}$")
    source_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_action(self) -> CorporateActionCreate:
        _require_timezone(self.effective_at, self.known_at)
        if self.action_type == "split":
            if self.split_factor is None or self.cash_amount_per_unit is not None:
                raise ValueError("split requires only split_factor")
        elif self.cash_amount_per_unit is None or self.split_factor is not None:
            raise ValueError("cash_dividend requires only cash_amount_per_unit")
        return self


class MarketDataSetCreate(BaseModel):
    provider: str = Field(min_length=2, max_length=80)
    provider_version: str = Field(min_length=1, max_length=80)
    rights_basis: RightsBasis
    cutoff_at: datetime
    known_at: datetime
    prices: list[PriceObservationCreate] = Field(default_factory=list, max_length=100_000)
    corporate_actions: list[CorporateActionCreate] = Field(default_factory=list, max_length=20_000)

    @model_validator(mode="after")
    def validate_cutoffs(self) -> MarketDataSetCreate:
        _require_timezone(self.cutoff_at, self.known_at)
        for price in self.prices:
            _require_timezone(price.observed_at, price.known_at)
        if self.known_at < self.cutoff_at:
            raise ValueError("known_at cannot be earlier than cutoff_at")
        if not self.prices:
            raise ValueError("at least one price observation is required")
        if any(price.observed_at > self.cutoff_at for price in self.prices):
            raise ValueError("price observations cannot be later than cutoff_at")
        if any(price.known_at > self.known_at for price in self.prices):
            raise ValueError("price known_at cannot be later than the dataset known_at")
        if any(action.effective_at > self.cutoff_at for action in self.corporate_actions):
            raise ValueError("corporate-action effective_at cannot exceed dataset cutoff_at")
        if any(action.known_at > self.known_at for action in self.corporate_actions):
            raise ValueError("corporate-action known_at cannot exceed dataset known_at")
        return self


class MarketDataSetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    portfolio_id: UUID
    provider: str
    provider_version: str
    rights_basis: str
    cutoff_at: datetime
    known_at: datetime
    content_hash: str
    status: str
    created_at: datetime


class AnalyticsRecompute(BaseModel):
    market_data_set_id: UUID
    as_of: datetime
    known_at: datetime
    max_price_age_days: int = Field(default=7, ge=0, le=31)

    @model_validator(mode="after")
    def validate_timestamps(self) -> AnalyticsRecompute:
        _require_timezone(self.as_of, self.known_at)
        return self


class MetricRead(BaseModel):
    metric_code: str
    dimension_type: str
    dimension_id: str
    value: str | None
    unit: str
    status: str
    details: dict[str, Any] = Field(default_factory=dict)


class ValuationPositionRead(BaseModel):
    instrument_reference: str
    quantity: str
    cost_basis: str
    price: str | None
    price_as_of: datetime | None
    market_value: str | None
    weight: str | None
    status: str


class AnalyticsSnapshotDetail(AnalyticsSnapshot):
    snapshot_id: UUID
    known_at: datetime
    market_data_version: str
    methodology_version: str
    input_hash: str
    metrics_list: list[MetricRead]
    positions: list[ValuationPositionRead]


class ScenarioCreate(BaseModel):
    base_snapshot_id: UUID
    name: str = Field(min_length=2, max_length=160)
    price_shocks: dict[str, Decimal] = Field(default_factory=dict, max_length=200)
    allocations: dict[str, Decimal] = Field(default_factory=dict, max_length=200)

    @model_validator(mode="after")
    def validate_scenario(self) -> ScenarioCreate:
        if not self.price_shocks and not self.allocations:
            raise ValueError("provide at least one price shock or hypothetical allocation")
        if any(
            value < Decimal("-1") or value > Decimal("5") for value in self.price_shocks.values()
        ):
            raise ValueError("price shocks must be ratios between -1 and 5")
        if any(value < 0 for value in self.allocations.values()):
            raise ValueError("allocations cannot be negative")
        return self


class ScenarioRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    portfolio_id: UUID
    base_snapshot_id: UUID
    name: str
    status: str
    assumptions: dict[str, Any]
    results: dict[str, Any]
    constraint_results: list[dict[str, Any]]
    engine_version: str
    can_execute: Literal[False]
    input_hash: str
    created_at: datetime


class EvidenceClaimCreate(BaseModel):
    claim_key: str = Field(min_length=1, max_length=128, pattern=r"^[a-zA-Z0-9_.:-]+$")
    statement: str = Field(min_length=1, max_length=500)
    numeric_value: Decimal | None = Field(default=None, decimal_places=12)
    unit: str | None = Field(default=None, max_length=24)


class EvidenceCreate(BaseModel):
    source_type: Literal["market", "fundamentals", "news", "sentiment", "research"]
    title: str = Field(min_length=2, max_length=255)
    publisher: str = Field(min_length=2, max_length=160)
    published_at: datetime
    retrieved_at: datetime
    known_at: datetime
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    locator: dict[str, Any] = Field(default_factory=dict)
    claims: list[EvidenceClaimCreate] = Field(min_length=1, max_length=100)
    quality: Literal["reviewed", "verified"]
    rights_basis: RightsBasis
    cutoff_eligible: bool = True

    @model_validator(mode="after")
    def validate_evidence_time(self) -> EvidenceCreate:
        _require_timezone(self.published_at, self.retrieved_at, self.known_at)
        if self.retrieved_at < self.published_at:
            raise ValueError("retrieved_at cannot be earlier than published_at")
        if self.known_at < self.retrieved_at:
            raise ValueError("known_at cannot be earlier than retrieved_at")
        return self


class EvidenceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    portfolio_id: UUID
    source_type: str
    title: str
    publisher: str
    published_at: datetime
    retrieved_at: datetime
    known_at: datetime
    content_hash: str
    locator: dict[str, Any]
    claims: list[dict[str, Any]]
    quality: str
    rights_basis: str
    cutoff_eligible: bool
    created_at: datetime


class AgentRunStart(BaseModel):
    run_id: UUID
    thread_id: UUID
    request_id: str = Field(min_length=8, max_length=96)
    question_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    as_of: datetime
    known_at: datetime
    graph_version: str = Field(min_length=1, max_length=64)
    prompt_bundle_version: str = Field(min_length=1, max_length=64)
    model_route: str = Field(min_length=1, max_length=80)
    policy_version: str = Field(min_length=1, max_length=64)
    allowed_tools: list[Literal["core.analytics.read", "core.evidence.read"]] = Field(max_length=2)
    checkpoint_thread_id: str = Field(min_length=32, max_length=255)

    @model_validator(mode="after")
    def validate_run_time(self) -> AgentRunStart:
        _require_timezone(self.as_of, self.known_at)
        if self.known_at < self.as_of:
            raise ValueError("known_at cannot be earlier than as_of")
        return self


class NumericCitation(BaseModel):
    claim_key: str = Field(min_length=1, max_length=128)
    evidence_id: str = Field(min_length=1, max_length=128)
    value: str = Field(min_length=1, max_length=80)
    unit: str = Field(min_length=1, max_length=24)
    as_of: datetime
    locator: str = Field(min_length=1, max_length=255)

    @model_validator(mode="after")
    def validate_as_of(self) -> NumericCitation:
        _require_timezone(self.as_of)
        return self


class AgentProposalWrite(BaseModel):
    type: str
    status: str
    title: str
    candidate_actions: list[dict[str, str]] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    can_execute: Literal[False]


class AgentRunComplete(BaseModel):
    state: Literal["completed", "failed", "timed_out"]
    intent: str | None = Field(default=None, max_length=40)
    stages: list[str] = Field(default_factory=list, max_length=30)
    citations: list[NumericCitation] = Field(default_factory=list, max_length=500)
    policy: dict[str, Any] = Field(default_factory=dict)
    proposal: AgentProposalWrite | None = None
    numeric_citation_coverage: Decimal = Field(default=Decimal("1"), ge=0, le=1)
    answer: str | None = Field(default=None, min_length=1, max_length=30_000)
    answer_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    error_code: str | None = Field(default=None, max_length=64)

    @model_validator(mode="after")
    def validate_terminal_shape(self) -> AgentRunComplete:
        if self.state == "completed":
            if (
                self.answer is None
                or self.answer_hash is None
                or self.proposal is None
                or self.error_code is not None
            ):
                raise ValueError(
                    "completed runs require answer, answer_hash, and proposal without error_code"
                )
        elif (
            self.answer is not None
            or self.answer_hash is not None
            or self.proposal is not None
            or bool(self.citations)
            or not self.error_code
        ):
            raise ValueError(
                "failed and timed-out runs require error_code and cannot publish answer evidence"
            )
        return self


class AgentRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    portfolio_id: UUID
    thread_id: UUID
    request_id: str
    intent: str | None
    as_of: datetime
    known_at: datetime
    graph_version: str
    prompt_bundle_version: str
    model_route: str
    policy_version: str
    allowed_tools: list[str]
    state: str
    stages: list[str]
    citations: list[dict[str, Any]]
    policy: dict[str, Any]
    result_hash: str | None
    error_code: str | None
    can_execute: Literal[False]
    started_at: datetime
    completed_at: datetime | None


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
