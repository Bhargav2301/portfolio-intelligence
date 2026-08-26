from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import httpx
from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field

from portfolio_agents.graph import graph
from portfolio_agents.settings import get_agent_settings


class AgentRunRequest(BaseModel):
    portfolio_id: str = Field(min_length=1)
    question: str = Field(min_length=2, max_length=4_000)
    as_of: datetime | None = None


class AgentRunResponse(BaseModel):
    run_id: str
    state: str
    answer: str
    stages: list[str]
    policy: dict
    evidence: list[dict]
    limitations: list[str]
    as_of: datetime


app = FastAPI(
    title="Portfolio Intelligence Agent API",
    version="0.1.0",
    description=(
        "Bounded LangGraph workflow for portfolio explanation and scenario review. "
        "The service has no order execution tools."
    ),
)


@app.get("/health/live")
async def live() -> dict[str, str]:
    return {"status": "live", "service": "portfolio-agents"}


@app.get("/health/ready")
async def ready() -> dict[str, str | bool]:
    settings = get_agent_settings()
    return {
        "status": "ready",
        "service": "portfolio-agents",
        "live_model_enabled": settings.live_model_enabled,
        "checkpoint_mode": "memory-development",
    }


@app.post("/v1/agent-runs", response_model=AgentRunResponse)
async def create_agent_run(payload: AgentRunRequest) -> AgentRunResponse:
    settings = get_agent_settings()
    run_id = str(uuid4())
    as_of = payload.as_of or datetime.now(timezone.utc)
    try:
        async with httpx.AsyncClient(
            base_url=settings.core_api_url,
            timeout=20,
            headers={"X-Workspace-Id": settings.dev_workspace_id},
        ) as client:
            response = await client.get(
                f"/v1/portfolios/{payload.portfolio_id}/analytics/latest"
            )
            response.raise_for_status()
            snapshot = response.json()
    except httpx.HTTPStatusError as error:
        if error.response.status_code == 404:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "PORTFOLIO_NOT_FOUND", "message": "Portfolio not found."},
            ) from error
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"code": "CORE_API_ERROR", "message": "Portfolio data could not be loaded."},
        ) from error
    except httpx.HTTPError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "CORE_API_UNAVAILABLE", "message": "Core API is unavailable."},
        ) from error

    state = await graph.ainvoke(
        {
            "run_id": run_id,
            "tenant_id": settings.dev_workspace_id,
            "portfolio_id": payload.portfolio_id,
            "as_of": as_of.isoformat(),
            "question": payload.question,
            "snapshot": snapshot,
            "stages": [],
            "evidence": [],
            "limitations": [],
        },
        config={
            "configurable": {"thread_id": run_id},
            "recursion_limit": settings.agent_max_steps + 2,
        },
    )
    return AgentRunResponse(
        run_id=run_id,
        state="completed",
        answer=state["answer"],
        stages=state.get("stages") or [],
        policy=state.get("policy") or {},
        evidence=state.get("evidence") or [],
        limitations=state.get("limitations") or [],
        as_of=as_of,
    )

