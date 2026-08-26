from __future__ import annotations

from datetime import date, datetime, timezone
from enum import Enum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class RunMode(str, Enum):
    REVIEW = "review"
    WEEKLY_TRIGGER = "weekly_trigger"


class RunStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    BLOCKED = "blocked"
    FAILED = "failed"


class EventLevel(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class HoldingSnapshot(StrictModel):
    symbol: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=160)
    exchange: Literal["NSE", "BSE", "NASDAQ", "NYSE"]
    analysis_symbol: str | None = Field(default=None, max_length=40)
    quantity: Annotated[float, Field(gt=0)]
    average_cost: Annotated[float, Field(ge=0)]
    current_price: Annotated[float, Field(ge=0)]
    market_value: Annotated[float, Field(ge=0)]
    allocation_percent: Annotated[float, Field(ge=0, le=100)]
    price_as_of: datetime

    @field_validator("symbol", "analysis_symbol")
    @classmethod
    def upper_symbols(cls, value: str | None) -> str | None:
        return value.upper() if value else value


class PortfolioPolicy(StrictModel):
    reserve_floor_inr: Annotated[float, Field(ge=0)] = 0
    deployable_cash_inr: Annotated[float, Field(ge=0)] = 0
    max_position_weight_percent: Annotated[float, Field(gt=0, le=100)] = 20
    max_single_deployment_inr: Annotated[float, Field(ge=0)] = 0
    data_max_age_minutes: Annotated[int, Field(ge=1, le=43200)] = 1440
    no_equal_weighting: bool = True
    require_human_confirmation: Literal[True] = True


class AnalysisRunRequest(StrictModel):
    portfolio_id: str = Field(min_length=1, max_length=128)
    snapshot_id: str = Field(min_length=8, max_length=128)
    snapshot_hash: str = Field(min_length=16, max_length=128)
    as_of: datetime
    analysis_date: date
    mode: RunMode = RunMode.WEEKLY_TRIGGER
    holdings: list[HoldingSnapshot] = Field(min_length=1, max_length=100)
    selected_symbols: list[str] = Field(default_factory=list, max_length=100)
    selected_analysts: list[Literal["market", "social", "news", "fundamentals"]] = Field(
        default_factory=lambda: ["market", "social", "news", "fundamentals"],
        min_length=1,
        max_length=4,
    )
    policy: PortfolioPolicy = Field(default_factory=PortfolioPolicy)
    dry_run: bool = False

    @field_validator("selected_symbols")
    @classmethod
    def normalize_symbols(cls, values: list[str]) -> list[str]:
        normalized = [value.strip().upper() for value in values if value.strip()]
        if len(normalized) != len(set(normalized)):
            raise ValueError("selected_symbols contains duplicates")
        return normalized

    @model_validator(mode="after")
    def selected_holdings_exist(self) -> "AnalysisRunRequest":
        known = {holding.symbol for holding in self.holdings}
        missing = set(self.selected_symbols) - known
        if missing:
            raise ValueError(f"selected symbols are absent from the snapshot: {', '.join(sorted(missing))}")
        return self


class PolicyCheck(StrictModel):
    code: str
    severity: Literal["pass", "warning", "block"]
    message: str
    symbol: str | None = None


class RunEvent(StrictModel):
    sequence: int
    occurred_at: datetime
    level: EventLevel
    stage: str
    message: str
    symbol: str | None = None


class SymbolResult(StrictModel):
    symbol: str
    analysis_symbol: str
    rating: Literal["Buy", "Overweight", "Hold", "Underweight", "Sell", "Unknown"]
    executive_summary: str
    investment_thesis: str
    trader_action: Literal["Buy", "Hold", "Sell", "Unknown"]
    trader_reasoning: str
    research_judgement: str
    risk_judgement: str
    policy_checks: list[PolicyCheck]
    reports: dict[str, str]


class AnalysisRun(StrictModel):
    id: str
    owner_email: str
    portfolio_id: str
    snapshot_id: str
    snapshot_hash: str
    mode: RunMode
    status: RunStatus
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    selected_symbols: list[str]
    policy_checks: list[PolicyCheck]
    results: list[SymbolResult] = Field(default_factory=list)
    error: str | None = None
    last_event_sequence: int = 0
    workflow_engine: Literal["langgraph"] = "langgraph"
    workflow_version: str = "pi-portfolio-v1"


class ChatRequest(StrictModel):
    prompt: str = Field(min_length=1, max_length=2000)
    run_id: str | None = None


class ChatAnswer(StrictModel):
    answer: str
    run_id: str
    as_of: datetime
    status: Literal["grounded", "restricted"]
    cited_symbols: list[str]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)
