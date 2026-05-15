from __future__ import annotations

import hmac
import os
import re
from dataclasses import dataclass
from typing import Any

from fastapi import Header, HTTPException, Request, status


TENANT_ID_PATTERN = re.compile(r"^[A-Za-z0-9_.:-]{1,64}$")
PUBLIC_PATHS = {"/", "/health"}
SECRET_NAMES = (
    "REALITY_OS_API_KEY",
    "REALITY_OS_SERVER_API_KEY",
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "DATABASE_URL",
)


@dataclass(frozen=True)
class ApiContext:
    tenant_id: str
    user_id: str
    auth_required: bool


def api_auth_required() -> bool:
    configured = os.getenv("REALITY_OS_API_AUTH_REQUIRED")
    if configured is not None:
        return configured.strip().lower() in {"1", "true", "yes", "on"}
    return os.getenv("REALITY_OS_ENV", "").strip().lower() in {"prod", "production"}


def expected_api_key() -> str | None:
    return os.getenv("REALITY_OS_API_KEY") or os.getenv("REALITY_OS_SERVER_API_KEY")


async def require_api_context(
    request: Request,
    x_reality_os_api_key: str | None = Header(default=None),
    x_tenant_id: str | None = Header(default=None),
    x_user_id: str | None = Header(default=None),
) -> ApiContext | None:
    if request.url.path in PUBLIC_PATHS:
        return None

    required = api_auth_required()
    tenant_id = (x_tenant_id or os.getenv("REALITY_OS_DEFAULT_TENANT") or "local").strip()
    if not TENANT_ID_PATTERN.fullmatch(tenant_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid tenant id")

    if required:
        expected = expected_api_key()
        if not expected:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="API auth is required but no server API key is configured",
            )
        if not hmac.compare_digest(x_reality_os_api_key or "", expected):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")
        if not x_tenant_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="X-Tenant-ID is required")

    context = ApiContext(
        tenant_id=tenant_id,
        user_id=(x_user_id or "local-user")[:80],
        auth_required=required,
    )
    request.state.api_context = context
    return context


def current_context(request: Request) -> ApiContext:
    context = getattr(request.state, "api_context", None)
    if isinstance(context, ApiContext):
        return context
    return ApiContext(
        tenant_id=os.getenv("REALITY_OS_DEFAULT_TENANT", "local"),
        user_id="local-user",
        auth_required=api_auth_required(),
    )


def secret_status() -> dict[str, Any]:
    return {
        "server_only": True,
        "values_exposed": False,
        "auth_required": api_auth_required(),
        "configured": {name: bool(os.getenv(name)) for name in SECRET_NAMES},
    }

