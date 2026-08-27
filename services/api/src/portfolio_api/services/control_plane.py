from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from portfolio_api.config import Settings
from portfolio_api.models import AuditEvent, IdempotencyRecord
from portfolio_api.observability import current_trace_id
from portfolio_api.tenant import RequestContext


def canonical_hash(value: Any) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
        ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def parse_etag(value: str | None, *, resource: str) -> int:
    if not value:
        raise HTTPException(
            status_code=status.HTTP_428_PRECONDITION_REQUIRED,
            detail={"code": "IF_MATCH_REQUIRED", "message": f"{resource} requires If-Match."},
        )
    normalized = value.strip().removeprefix("W/").strip('"')
    try:
        return int(normalized)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_ETAG", "message": "If-Match must contain a version."},
        ) from error


def require_version(expected: int, actual: int, *, resource: str) -> None:
    if expected != actual:
        raise HTTPException(
            status_code=status.HTTP_412_PRECONDITION_FAILED,
            detail={
                "code": "STALE_VERSION",
                "message": f"{resource} changed; reload it before continuing.",
                "current_version": actual,
            },
        )


def require_recent_owner(context: RequestContext, settings: Settings) -> None:
    if context.role != "owner":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "OWNER_REQUIRED", "message": "Only the portfolio owner may publish."},
        )
    if not context.has_recent_auth(settings.step_up_max_age_seconds):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "STEP_UP_REQUIRED",
                "message": "Reauthenticate with MFA before this action.",
            },
        )
    verified_methods = {method.lower() for method in context.authentication_methods}
    if not verified_methods.intersection({"mfa", "totp", "webauthn", "passkey", "development"}):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "MFA_REQUIRED",
                "message": "A verified passkey or TOTP authentication is required.",
            },
        )


async def idempotent_replay(
    session: AsyncSession,
    context: RequestContext,
    *,
    endpoint: str,
    key: str | None,
    request_body: Any,
) -> tuple[str, dict[str, Any] | None, int | None]:
    if not key or not key.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "IDEMPOTENCY_KEY_REQUIRED", "message": "Idempotency-Key is required."},
        )
    normalized_key = key.strip()
    if len(normalized_key) > 160:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_IDEMPOTENCY_KEY", "message": "Idempotency-Key is too long."},
        )
    request_hash = canonical_hash(request_body)
    record = await session.scalar(
        select(IdempotencyRecord).where(
            IdempotencyRecord.tenant_id == context.tenant_id,
            IdempotencyRecord.principal_id == context.user_id,
            IdempotencyRecord.endpoint == endpoint,
            IdempotencyRecord.idempotency_key == normalized_key,
        )
    )
    if record is None:
        return request_hash, None, None
    if record.request_hash != request_hash:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "IDEMPOTENCY_PAYLOAD_CONFLICT",
                "message": "This Idempotency-Key was already used with another payload.",
            },
        )
    return request_hash, dict(record.response_body), record.status_code


def store_idempotency(
    session: AsyncSession,
    context: RequestContext,
    settings: Settings,
    *,
    endpoint: str,
    key: str,
    request_hash: str,
    status_code: int,
    response_body: dict[str, Any],
) -> IdempotencyRecord:
    record = IdempotencyRecord(
        tenant_id=context.tenant_id,
        principal_id=context.user_id,
        endpoint=endpoint,
        idempotency_key=key.strip(),
        request_hash=request_hash,
        status_code=status_code,
        response_body=response_body,
        expires_at=datetime.now(UTC) + timedelta(hours=settings.idempotency_retention_hours),
    )
    session.add(record)
    return record


def audit_event(
    context: RequestContext,
    *,
    action: str,
    resource_type: str,
    resource_id: UUID | None,
    details: dict[str, Any] | None = None,
) -> AuditEvent:
    safe_details = details or {}
    forbidden = {"token", "secret", "document", "prompt", "order_payload", "account_number"}
    if any(key.lower() in forbidden for key in safe_details):
        raise ValueError("Sensitive fields are not allowed in audit details")
    return AuditEvent(
        tenant_id=context.tenant_id,
        actor_id=context.user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        trace_id=current_trace_id(),
        details=safe_details,
    )
