from __future__ import annotations

import json
import logging
import re
import time
from contextvars import ContextVar
from uuid import uuid4

from fastapi import FastAPI, Request, Response

from portfolio_api.config import Settings

_trace_id: ContextVar[str | None] = ContextVar("trace_id", default=None)
_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)
_request_id_pattern = re.compile(r"^[0-9a-fA-F-]{36}$")


def current_trace_id() -> str | None:
    return _trace_id.get()


def current_request_id() -> str | None:
    return _request_id.get()


def _trace_from_header(value: str | None) -> str:
    if value:
        parts = value.split("-")
        if (
            len(parts) == 4
            and len(parts[1]) == 32
            and all(character in "0123456789abcdefABCDEF" for character in parts[1])
        ):
            return parts[1].lower()
    return uuid4().hex


def install_request_telemetry(app: FastAPI, settings: Settings) -> None:
    logger = logging.getLogger(settings.service_name)

    @app.middleware("http")
    async def request_telemetry(request: Request, call_next):
        supplied_request_id = request.headers.get("X-Request-Id")
        request_id = (
            supplied_request_id
            if supplied_request_id and _request_id_pattern.fullmatch(supplied_request_id)
            else str(uuid4())
        )
        trace_id = _trace_from_header(request.headers.get("traceparent"))
        request_token = _request_id.set(request_id)
        trace_token = _trace_id.set(trace_id)
        started = time.perf_counter()
        status_code = 500
        try:
            response: Response = await call_next(request)
            status_code = response.status_code
            response.headers["X-Request-Id"] = request_id
            response.headers["traceparent"] = f"00-{trace_id}-{'0' * 16}-01"
            return response
        finally:
            event = {
                "event": "http.request",
                "service": settings.service_name,
                "environment": settings.app_env,
                "method": request.method,
                "route": getattr(request.scope.get("route"), "path", "unmatched"),
                "status_code": status_code,
                "duration_ms": round((time.perf_counter() - started) * 1_000, 2),
                "request_id": request_id,
                "trace_id": trace_id,
            }
            logger.info(json.dumps(event, separators=(",", ":"), sort_keys=True))
            _request_id.reset(request_token)
            _trace_id.reset(trace_token)


def configure_opentelemetry(app: FastAPI, settings: Settings) -> bool:
    """Configure metadata-only tracing. Request and response bodies are never captured."""
    if not settings.otel_exporter_otlp_endpoint:
        return False
    try:
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
    except ImportError as error:
        if settings.requires_oidc:
            raise RuntimeError(
                "OpenTelemetry dependencies are required outside development"
            ) from error
        return False

    provider = TracerProvider(
        resource=Resource.create(
            {"service.name": settings.service_name, "deployment.environment": settings.app_env}
        )
    )
    provider.add_span_processor(
        BatchSpanProcessor(OTLPSpanExporter(endpoint=settings.otel_exporter_otlp_endpoint))
    )
    tracer = provider.get_tracer(settings.service_name)

    propagator = TraceContextTextMapPropagator()

    @app.middleware("http")
    async def safe_trace(request: Request, call_next):
        if request.url.path in {"/health/live", "/health/ready"}:
            return await call_next(request)
        parent = propagator.extract(dict(request.headers))
        with tracer.start_as_current_span(
            "http.request",
            context=parent,
            attributes={
                "service.name": settings.service_name,
                "deployment.environment": settings.app_env,
                "http.request.method": request.method,
            },
        ) as span:
            response = await call_next(request)
            span.set_attribute(
                "http.route", getattr(request.scope.get("route"), "path", "unmatched")
            )
            span.set_attribute("http.response.status_code", response.status_code)
            return response

    return True
