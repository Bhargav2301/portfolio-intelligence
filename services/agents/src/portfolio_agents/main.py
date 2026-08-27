from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Literal
from urllib.parse import quote, urlsplit, urlunsplit
from uuid import UUID, uuid4

import httpx
from fastapi import FastAPI, Header, HTTPException, Request, status
from pydantic import BaseModel, Field

from portfolio_agents.graph import build_graph
from portfolio_agents.graph import graph as development_graph
from portfolio_agents.settings import get_agent_settings


async def _checkpoint_dsn() -> str:
    settings = get_agent_settings()
    assert settings.postgres_checkpoint_dsn is not None
    if not settings.rds_iam_auth:
        return settings.postgres_checkpoint_dsn
    import boto3

    parsed = urlsplit(settings.postgres_checkpoint_dsn)
    if not parsed.hostname or not parsed.username:
        raise RuntimeError("POSTGRES_CHECKPOINT_DSN must include host and spi_checkpoint user.")
    port = parsed.port or 5432
    token = await asyncio.to_thread(
        boto3.client("rds", region_name=settings.aws_region).generate_db_auth_token,
        DBHostname=parsed.hostname,
        Port=port,
        DBUsername=parsed.username,
        Region=settings.aws_region,
    )
    host = parsed.hostname if port == 5432 else f"{parsed.hostname}:{port}"
    netloc = f"{quote(parsed.username)}:{quote(token, safe='')}@{host}"
    query = parsed.query or "sslmode=require"
    return urlunsplit((parsed.scheme, netloc, parsed.path, query, parsed.fragment))


class AgentRunRequest(BaseModel):
    portfolio_id: str = Field(min_length=1)
    question: str = Field(min_length=2, max_length=4_000)
    instrument: str | None = Field(default=None, min_length=1, max_length=32)
    as_of: datetime | None = None


class AgentProposal(BaseModel):
    type: str
    status: str
    title: str
    candidate_actions: list[dict[str, str]] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    can_execute: Literal[False]


class AgentRunResponse(BaseModel):
    run_id: str
    state: str
    answer: str
    stages: list[str]
    policy: dict
    evidence: list[dict]
    limitations: list[str]
    proposal: AgentProposal
    perspectives: dict[str, str]
    telemetry: dict
    as_of: datetime


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_agent_settings()
    if settings.requires_oidc:
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

        async with AsyncPostgresSaver.from_conn_string(await _checkpoint_dsn()) as checkpointer:
            await checkpointer.setup()
            app.state.graph = build_graph(settings, checkpointer)
            app.state.checkpoint_mode = "postgres-durable"
            yield
        return
    app.state.graph = development_graph
    app.state.checkpoint_mode = "memory-development"
    yield


app = FastAPI(
    title="Portfolio Intelligence Agent API",
    version="0.2.0",
    description=(
        "Bounded LangGraph workflow for evidence-linked portfolio research. "
        "Every proposal is structurally non-executable."
    ),
    lifespan=lifespan,
)


@app.get("/health/live")
async def live() -> dict[str, str]:
    return {"status": "live", "service": "portfolio-agents"}


@app.get("/health/ready")
async def ready(request: Request) -> dict[str, str | bool]:
    settings = get_agent_settings()
    return {
        "status": "ready",
        "service": "portfolio-agents",
        "live_model_enabled": settings.live_model_enabled,
        "checkpoint_mode": getattr(request.app.state, "checkpoint_mode", "initializing"),
        "can_execute": False,
    }


@app.post("/v1/agent-runs", response_model=AgentRunResponse)
async def create_agent_run(
    payload: AgentRunRequest,
    request: Request,
    authorization: str | None = Header(default=None, alias="Authorization"),
    x_workspace_id: str | None = Header(default=None, alias="X-Workspace-Id"),
) -> AgentRunResponse:
    settings = get_agent_settings()
    if settings.requires_oidc and (
        not authorization or not authorization.startswith("Bearer ") or not x_workspace_id
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "AUTHENTICATION_REQUIRED", "message": "Sign in is required."},
        )
    run_id = str(uuid4())
    as_of = payload.as_of or datetime.now(UTC)
    try:
        workspace_id = str(UUID(x_workspace_id or settings.dev_workspace_id))
        portfolio_id = str(UUID(payload.portfolio_id))
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_SCOPE", "message": "Invalid workspace or portfolio ID."},
        ) from error
    core_headers = {"X-Workspace-Id": workspace_id}
    if authorization:
        core_headers["Authorization"] = authorization
    try:
        async with httpx.AsyncClient(
            base_url=settings.core_api_url,
            timeout=20,
            headers=core_headers,
        ) as client:
            response = await client.get(f"/v1/portfolios/{portfolio_id}/agent-context")
            response.raise_for_status()
            context = response.json()
    except httpx.HTTPStatusError as error:
        if error.response.status_code in {401, 403}:
            raise HTTPException(
                status_code=error.response.status_code,
                detail={"code": "AGENT_SCOPE_DENIED", "message": "Portfolio access was denied."},
            ) from error
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

    ledger = context.get("ledger") or {}
    snapshot = {
        "quality_state": "trusted" if int(ledger.get("ledger_version", 0)) > 0 else "partial",
        "metrics": {
            "current_value": ledger.get("total_value"),
            "net_invested_capital": ledger.get("net_invested_capital"),
            "cash_balance": ledger.get("cash_balance"),
            "securities_market_value": ledger.get("securities_market_value"),
        },
        "rules": (context.get("portfolio") or {}).get("rules") or {},
        "limitations": ledger.get("limitations") or [],
    }
    graph_instance = request.app.state.graph
    try:
        async with asyncio.timeout(settings.agent_timeout_seconds):
            state = await graph_instance.ainvoke(
                {
                    "run_id": run_id,
                    "tenant_id": workspace_id,
                    "portfolio_id": portfolio_id,
                    "as_of": as_of.isoformat(),
                    "question": payload.question,
                    "instrument": payload.instrument.upper() if payload.instrument else None,
                    "snapshot": snapshot,
                    "context": context,
                    "stages": [],
                    "evidence": [],
                    "limitations": [],
                },
                config={
                    "configurable": {"thread_id": run_id},
                    "recursion_limit": settings.agent_max_steps + 2,
                },
            )
    except TimeoutError as error:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail={"code": "AGENT_TIMEOUT", "message": "The bounded agent run timed out."},
        ) from error
    proposal = AgentProposal.model_validate(state.get("proposal") or {})
    return AgentRunResponse(
        run_id=run_id,
        state="completed",
        answer=state["answer"],
        stages=state.get("stages") or [],
        policy=state.get("policy") or {},
        evidence=state.get("evidence") or [],
        limitations=state.get("limitations") or [],
        proposal=proposal,
        perspectives=state.get("perspectives") or {},
        telemetry=state.get("telemetry") or {},
        as_of=as_of,
    )
