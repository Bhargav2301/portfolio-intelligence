from __future__ import annotations

from uuid import UUID

from fastapi import FastAPI, HTTPException

from portfolio_intelligence.api.schemas import RecommendationIn, TransactionIn
from portfolio_intelligence.application.services import PortfolioService, RecommendationService
from portfolio_intelligence.config import Settings
from portfolio_intelligence.domain.evidence import EvidenceItem
from portfolio_intelligence.domain.ledger import (
    DuplicateTransactionError,
    InvalidLedgerOperation,
    PortfolioLedger,
)
from portfolio_intelligence.domain.models import Transaction
from portfolio_intelligence.domain.recommendation import RecommendationRequest

settings = Settings.from_environment()
portfolio_service = PortfolioService(PortfolioLedger())
recommendation_service = RecommendationService.from_settings(settings)

app = FastAPI(
    title="Portfolio Intelligence API",
    version="0.1.0",
    description="Deterministic portfolio services with evidence-gated recommendations.",
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "environment": settings.environment}


@app.post("/v1/portfolios/{portfolio_id}/transactions", status_code=201)
def record_transaction(portfolio_id: str, payload: TransactionIn) -> dict[str, str]:
    try:
        portfolio_uuid = UUID(portfolio_id)
    except ValueError as error:
        raise HTTPException(status_code=422, detail="portfolio_id must be a UUID") from error

    try:
        transaction = Transaction(portfolio_id=portfolio_uuid, **payload.model_dump())
        recorded = portfolio_service.record_transaction(transaction)
    except (ValueError, DuplicateTransactionError, InvalidLedgerOperation) as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return {"transaction_id": str(recorded.id), "status": "recorded"}


@app.get("/v1/portfolios/{portfolio_id}/positions")
def positions(portfolio_id: str) -> list[dict[str, str]]:
    try:
        portfolio_uuid = UUID(portfolio_id)
    except ValueError as error:
        raise HTTPException(status_code=422, detail="portfolio_id must be a UUID") from error
    return [
        {
            "instrument_id": str(position.instrument_id),
            "quantity": str(position.quantity),
            "average_cost": str(position.average_cost),
            "cost_basis": str(position.cost_basis),
            "realized_gain": str(position.realized_gain),
        }
        for position in portfolio_service.positions(portfolio_uuid).values()
    ]


@app.post("/v1/recommendations/evaluate")
def evaluate_recommendation(payload: RecommendationIn) -> dict[str, object]:
    evidence = tuple(EvidenceItem(**item.model_dump()) for item in payload.evidence)
    request_data = payload.model_dump(exclude={"evidence"})
    decision = recommendation_service.evaluate(
        RecommendationRequest(**request_data, evidence=evidence)
    )
    return {
        "allowed": decision.allowed,
        "final_stance": decision.final_stance,
        "reasons": decision.reasons,
        "evidence_ids": decision.evidence_ids,
        "policy_version": decision.policy_version,
    }
