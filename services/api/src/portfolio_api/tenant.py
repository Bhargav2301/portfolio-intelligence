from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from fastapi import Header, HTTPException, status

from portfolio_api.config import get_settings


@dataclass(frozen=True)
class RequestContext:
    tenant_id: UUID
    user_id: UUID


async def request_context(
    x_workspace_id: str | None = Header(default=None, alias="X-Workspace-Id"),
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
) -> RequestContext:
    settings = get_settings()
    if settings.is_production:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "PRODUCTION_AUTH_NOT_ENABLED",
                "message": "OIDC authentication middleware must be enabled before production use.",
            },
        )
    try:
        tenant_id = UUID(x_workspace_id) if x_workspace_id else settings.dev_workspace_id
        user_id = UUID(x_user_id) if x_user_id else settings.dev_user_id
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_IDENTITY_CONTEXT", "message": "Invalid workspace or user ID."},
        ) from error
    return RequestContext(tenant_id=tenant_id, user_id=user_id)

