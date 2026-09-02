from __future__ import annotations

import asyncio
import os

from fastapi import (
    BackgroundTasks,
    Depends,
    FastAPI,
    Header,
    HTTPException,
    WebSocket,
    WebSocketDisconnect,
    status,
)

from .models import (
    AnalysisRun,
    AnalysisRunRequest,
    ChatAnswer,
    ChatRequest,
    RunStatus,
    utc_now,
)
from .orchestration import RunCoordinator

app = FastAPI(title="PI TradingAgents Runtime", version="0.3.0", docs_url="/docs")
coordinator = RunCoordinator.production_default()


def authenticated_owner(
    authorization: str | None = Header(default=None),
    x_pi_owner_email: str | None = Header(default=None),
) -> str:
    if os.getenv("PI_ALLOW_INSECURE_LOCAL", "false").lower() == "true":
        return x_pi_owner_email or "local@example.invalid"
    expected = os.getenv("PI_INTERNAL_API_TOKEN")
    if not expected or authorization != f"Bearer {expected}" or not x_pi_owner_email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized",
        )
    return x_pi_owner_email.lower()


def owned_run(run_id: str, owner_email: str) -> AnalysisRun:
    run = coordinator.store.get(run_id)
    if not run or run.owner_email != owner_email:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


@app.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "runtime": "tradingagents",
        "orchestration": "langgraph",
        "workflow": "pi-portfolio-v1",
        "resilience": "per-symbol-abstention",
        "version": "0.3.0",
    }


@app.post("/v1/runs", response_model=AnalysisRun, status_code=202)
async def create_run(
    request: AnalysisRunRequest,
    background_tasks: BackgroundTasks,
    owner_email: str = Depends(authenticated_owner),
) -> AnalysisRun:
    run = coordinator.create(owner_email, request)
    if run.status != RunStatus.BLOCKED:
        background_tasks.add_task(coordinator.execute, run.id, request)
    return run


@app.get("/v1/runs/{run_id}", response_model=AnalysisRun)
def get_run(
    run_id: str,
    owner_email: str = Depends(authenticated_owner),
) -> AnalysisRun:
    return owned_run(run_id, owner_email)


@app.get("/v1/runs/{run_id}/events")
def get_events(
    run_id: str,
    after: int = 0,
    owner_email: str = Depends(authenticated_owner),
) -> dict[str, object]:
    owned_run(run_id, owner_email)
    events = coordinator.store.events(run_id, max(0, after))
    return {"events": events, "next": events[-1].sequence if events else after}


@app.websocket("/v1/ws/runs/{run_id}")
async def run_events(websocket: WebSocket, run_id: str) -> None:
    token = websocket.headers.get("authorization")
    owner = websocket.headers.get("x-pi-owner-email")
    try:
        owner_email = authenticated_owner(token, owner)
        owned_run(run_id, owner_email)
    except HTTPException:
        await websocket.close(code=4401)
        return
    await websocket.accept()
    after = 0
    try:
        while True:
            events = coordinator.store.events(run_id, after)
            for event in events:
                await websocket.send_json(event.model_dump(mode="json"))
                after = event.sequence
            run = owned_run(run_id, owner_email)
            if run.status in {
                RunStatus.COMPLETED,
                RunStatus.BLOCKED,
                RunStatus.FAILED,
            }:
                await websocket.send_json(
                    {"type": "terminal", "status": run.status.value}
                )
                await websocket.close()
                return
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        return


@app.post("/v1/chat", response_model=ChatAnswer)
def chat(
    request: ChatRequest,
    owner_email: str = Depends(authenticated_owner),
) -> ChatAnswer:
    run = (
        owned_run(request.run_id, owner_email)
        if request.run_id
        else coordinator.store.latest_for_owner(owner_email)
    )
    if not run:
        raise HTTPException(status_code=404, detail="No agent run is available")
    query = request.prompt.lower()
    restricted = any(
        term in query
        for term in ("place order", "execute", "buy for me", "sell for me")
    )
    if restricted:
        answer = (
            "Order execution is disabled. Agent output is research only and requires "
            "explicit human review."
        )
        symbols: list[str] = []
    elif run.status != RunStatus.COMPLETED:
        answer = (
            f"Run {run.id[:8]} is {run.status.value}. Review the live activity log "
            "for current progress."
        )
        symbols = []
    elif not run.results:
        answer = "The completed run contains no symbol results."
        symbols = []
    else:
        selected = next(
            (result for result in run.results if result.symbol.lower() in query),
            run.results[0],
        )
        symbols = [selected.symbol]
        if any(
            term in query
            for term in ("risk", "constraint", "policy", "overweight")
        ):
            reasons = " ".join(check.message for check in selected.policy_checks)
            answer = (
                f"{selected.symbol}: {selected.risk_judgement} "
                f"Independent PI policy: {reasons}"
            )
        elif any(term in query for term in ("why", "reason", "thesis", "strategy")):
            answer = (
                f"{selected.symbol} is rated {selected.rating}. "
                f"{selected.investment_thesis} "
                f"Trader summary: {selected.trader_reasoning}"
            )
        else:
            answer = (
                f"{selected.symbol} is rated {selected.rating}. "
                f"{selected.executive_summary}"
            )
    return ChatAnswer(
        answer=answer,
        run_id=run.id,
        as_of=run.completed_at or run.created_at or utc_now(),
        status="restricted" if restricted else "grounded",
        cited_symbols=symbols,
    )
