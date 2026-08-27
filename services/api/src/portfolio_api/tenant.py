from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime
from functools import lru_cache
from uuid import NAMESPACE_URL, UUID, uuid5

from fastapi import Header, HTTPException, status

from portfolio_api.config import get_settings


@dataclass
class RequestContext:
    tenant_id: UUID
    user_id: UUID
    identity_subject: str
    role: str = "unverified"
    auth_time: datetime = field(default_factory=lambda: datetime.now(UTC))
    authentication_methods: tuple[str, ...] = ()
    token_id: str | None = None

    def has_recent_auth(self, max_age_seconds: int) -> bool:
        age = (datetime.now(UTC) - self.auth_time).total_seconds()
        return 0 <= age <= max_age_seconds


@lru_cache(maxsize=4)
def _jwks_client(url: str):
    import jwt

    return jwt.PyJWKClient(url, cache_keys=True, lifespan=300)


def _decode_oidc_token(token: str) -> dict[str, object]:
    import jwt

    settings = get_settings()
    issuer = str(settings.oidc_issuer_url).rstrip("/")
    jwks_url = settings.oidc_jwks_url or f"{issuer}/.well-known/jwks.json"
    signing_key = _jwks_client(jwks_url).get_signing_key_from_jwt(token)
    claims = jwt.decode(
        token,
        signing_key.key,
        algorithms=["RS256"],
        issuer=issuer,
        options={"require": ["exp", "iat", "sub", "iss"], "verify_aud": False},
    )
    audience = claims.get("aud") or claims.get("client_id")
    valid_audience = (
        settings.oidc_client_id in audience
        if isinstance(audience, list)
        else audience == settings.oidc_client_id
    )
    if not valid_audience:
        raise jwt.InvalidAudienceError("Token was issued for another client")
    if claims.get("token_use") != "access":
        raise jwt.InvalidTokenError("Only access tokens may call the Core API")
    required_scopes = set(settings.oidc_required_scopes.split())
    supplied_scopes = set(str(claims.get("scope", "")).split())
    if not required_scopes.issubset(supplied_scopes):
        raise jwt.InvalidTokenError("Required scopes are missing")
    return claims


async def request_context(
    authorization: str | None = Header(default=None, alias="Authorization"),
    x_workspace_id: str | None = Header(default=None, alias="X-Workspace-Id"),
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
) -> RequestContext:
    settings = get_settings()
    if settings.requires_oidc:
        if not x_workspace_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "WORKSPACE_REQUIRED", "message": "Select a workspace."},
            )
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"code": "AUTHENTICATION_REQUIRED", "message": "Sign in is required."},
                headers={"WWW-Authenticate": "Bearer"},
            )
        try:
            tenant_id = UUID(x_workspace_id)
            claims = await asyncio.to_thread(_decode_oidc_token, authorization[7:])
            subject = str(claims["sub"])
            user_id = uuid5(NAMESPACE_URL, f"{settings.oidc_issuer_url}#{subject}")
            auth_time_value = int(claims.get("auth_time") or claims.get("iat") or 0)
            auth_time = datetime.fromtimestamp(auth_time_value, tz=UTC)
            raw_amr = claims.get("amr") or []
            amr = tuple(str(item) for item in raw_amr) if isinstance(raw_amr, list) else ()
            return RequestContext(
                tenant_id=tenant_id,
                user_id=user_id,
                identity_subject=subject,
                auth_time=auth_time,
                authentication_methods=amr,
                token_id=str(claims.get("jti")) if claims.get("jti") else None,
            )
        except HTTPException:
            raise
        except Exception as error:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"code": "INVALID_IDENTITY_TOKEN", "message": "Sign in again."},
                headers={"WWW-Authenticate": "Bearer"},
            ) from error

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
    return RequestContext(
        tenant_id=tenant_id,
        user_id=user_id,
        identity_subject=f"development:{user_id}",
        role="owner",
        authentication_methods=("development", "mfa"),
    )
