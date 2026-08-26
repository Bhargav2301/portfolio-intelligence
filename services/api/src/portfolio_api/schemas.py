from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


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


class ErrorBody(BaseModel):
    code: str
    message: str
    retryable: bool = False
    trace_id: str | None = None

