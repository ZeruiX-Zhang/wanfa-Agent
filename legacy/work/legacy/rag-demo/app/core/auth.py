from __future__ import annotations

import os

from fastapi import Header, HTTPException, Security
from fastapi.security import APIKeyHeader

from app.core.config import settings
from app.schemas.auth import AuthContext


DEMO_ROLES = ["employee", "support", "finance", "ops", "legal", "analyst", "manager"]
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def require_auth(
    authorization: str | None = Header(default=None),
    api_key: str | None = Security(api_key_header),
) -> AuthContext:
    if not _env_bool("AUTH_ENABLED", settings.auth_enabled):
        return AuthContext()

    expected = (os.getenv("DEMO_API_KEY") or settings.demo_api_key).strip()
    token = api_key if isinstance(api_key, str) else None
    if not token and isinstance(authorization, str) and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()

    if not token:
        raise HTTPException(status_code=401, detail="Missing API key")
    if token != expected:
        raise HTTPException(status_code=403, detail="Invalid API key")

    return AuthContext(
        user_id="demo-user",
        tenant_id="demo",
        roles=list(DEMO_ROLES),
    )


get_request_context = require_auth
