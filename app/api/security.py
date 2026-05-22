from __future__ import annotations

import secrets

from fastapi import Cookie, Header, HTTPException, Request

from app.config.settings import get_settings


_PROTECTED_ENVS = frozenset({"production", "staging"})
_ADMIN_COOKIE_NAME = "admin_token"


def _extract_bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None
    return token.strip() or None


async def require_admin_access(
    request: Request,
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
    authorization: str | None = Header(default=None),
    admin_token: str | None = Cookie(default=None, alias=_ADMIN_COOKIE_NAME),
) -> None:
    """Protect admin routes with a shared token outside development."""
    settings = getattr(request.app.state, "settings", None) or get_settings()
    expected = settings.admin_api_token.strip()
    environment = settings.app_env.lower()

    if not expected:
        if environment in _PROTECTED_ENVS:
            raise HTTPException(status_code=503, detail="Admin API token is not configured")
        return

    provided = x_admin_token or _extract_bearer_token(authorization) or admin_token
    if not provided or not secrets.compare_digest(provided, expected):
        raise HTTPException(
            status_code=401,
            detail="Admin authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
