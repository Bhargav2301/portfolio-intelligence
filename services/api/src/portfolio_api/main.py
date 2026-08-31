from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from portfolio_api.config import get_settings
from portfolio_api.database import close_database, initialize_database
from portfolio_api.observability import configure_opentelemetry, install_request_telemetry
from portfolio_api.routers import (
    analytics,
    health,
    intelligence,
    ledger,
    portfolios,
    reconciliation,
    uploads,
)

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    await initialize_database()
    yield
    await close_database()


app = FastAPI(
    title="Portfolio Intelligence Core API",
    version="0.3.0",
    description=(
        "Read-only portfolio system of record, secure file intake, and deterministic analytics. "
        "No order execution endpoints exist."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "Idempotency-Key",
        "If-Match",
        "traceparent",
        "X-CSRF-Token",
        "X-Request-Id",
        "X-Workspace-Id",
        *([] if settings.requires_oidc else ["X-User-Id"]),
    ],
)

install_request_telemetry(app, settings)
configure_opentelemetry(app, settings)

app.include_router(health.router)
app.include_router(portfolios.router)
app.include_router(uploads.router)
app.include_router(analytics.router)
app.include_router(ledger.router)
app.include_router(reconciliation.router)
app.include_router(intelligence.router)
