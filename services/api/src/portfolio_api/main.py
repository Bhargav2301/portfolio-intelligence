from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from portfolio_api.database import close_database, initialize_database
from portfolio_api.routers import analytics, health, portfolios, uploads


@asynccontextmanager
async def lifespan(_: FastAPI):
    await initialize_database()
    yield
    await close_database()


app = FastAPI(
    title="Portfolio Intelligence Core API",
    version="0.1.0",
    description=(
        "Read-only portfolio system of record, secure file intake, and deterministic analytics. "
        "No order execution endpoints exist."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Content-Type", "X-Workspace-Id", "X-User-Id", "Idempotency-Key"],
)

app.include_router(health.router)
app.include_router(portfolios.router)
app.include_router(uploads.router)
app.include_router(analytics.router)

