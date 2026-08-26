from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi.testclient import TestClient

from portfolio_intelligence.api.app import app
from portfolio_intelligence.domain.evidence import sha256_text

client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_record_transaction_and_read_position() -> None:
    portfolio_id = uuid4()
    instrument_id = uuid4()
    response = client.post(
        f"/v1/portfolios/{portfolio_id}/transactions",
        json={
            "instrument_id": str(instrument_id),
            "transaction_type": "buy",
            "quantity": "10",
            "unit_price": "100",
            "fees": "5",
            "currency": "INR",
            "occurred_at": datetime.now(UTC).isoformat(),
            "idempotency_key": f"api-test-{uuid4()}",
        },
    )

    assert response.status_code == 201
    positions = client.get(f"/v1/portfolios/{portfolio_id}/positions")
    assert positions.status_code == 200
    assert positions.json() == [
        {
            "instrument_id": str(instrument_id),
            "quantity": "10",
            "average_cost": "100.5",
            "cost_basis": "1005",
            "realized_gain": "0",
        }
    ]


def test_invalid_portfolio_id_is_rejected() -> None:
    response = client.get("/v1/portfolios/not-a-uuid/positions")

    assert response.status_code == 422
    assert response.json()["detail"] == "portfolio_id must be a UUID"


def test_stale_recommendation_fails_closed() -> None:
    now = datetime.now(UTC)
    content = "A primary-source exchange filing."
    response = client.post(
        "/v1/recommendations/evaluate",
        json={
            "classification": "attention_flag",
            "requested_stance": "hold",
            "instrument_id": str(uuid4()),
            "as_of": now.isoformat(),
            "market_data_as_of": (now - timedelta(hours=1)).isoformat(),
            "evidence": [
                {
                    "publisher": "Example Exchange",
                    "source_uri": "https://exchange.example/filing/1",
                    "title": "Material filing",
                    "source_tier": 1,
                    "published_at": (now - timedelta(hours=1)).isoformat(),
                    "retrieved_at": now.isoformat(),
                    "content_excerpt": content,
                    "content_hash": sha256_text(content),
                }
            ],
            "factual_claim_count": 1,
            "cited_claim_count": 1,
        },
    )

    assert response.status_code == 200
    assert response.json()["allowed"] is False
    assert response.json()["final_stance"] == "insufficient_evidence"
    assert "market data is stale" in response.json()["reasons"]
