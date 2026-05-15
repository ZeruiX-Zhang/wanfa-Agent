from __future__ import annotations

import hmac

from fastapi import Header, HTTPException, Security, status
from fastapi.security import APIKeyHeader

from platform_common.models import AuthContext
from platform_common.settings import get_settings


api_key_header = APIKeyHeader(
    name="X-API-Key",
    scheme_name="API 密钥",
    description="主鉴权头。启用鉴权时请填写平台 API Key；本地演示默认可使用 `change-me`。",
    auto_error=False,
)


def require_auth(
    authorization: str | None = Header(
        default=None,
        description="可选 Bearer Token；鉴权关闭时可留空。",
    ),
    api_key: str | None = Security(api_key_header),
    x_user_id: str | None = Header(
        default=None,
        description="当前用户 ID；不传则使用默认演示用户。",
    ),
    x_tenant_id: str | None = Header(
        default=None,
        description="当前租户 ID；不传则使用默认演示租户。",
    ),
    x_roles: str | None = Header(
        default=None,
        description="当前用户角色，多个角色使用逗号分隔；不传则使用默认角色。",
    ),
) -> AuthContext:
    settings = get_settings()
    token = api_key if isinstance(api_key, str) else None
    if not token and isinstance(authorization, str) and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()

    if settings.auth_enabled:
        if not token or not hmac.compare_digest(token, settings.api_key):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"code": "unauthorized", "message": "Missing or invalid API key"},
            )

    roles = (
        [item.strip() for item in x_roles.split(",") if item.strip()]
        if x_roles
        else settings.default_roles
    )
    return AuthContext(
        user_id=x_user_id or settings.default_user_id,
        tenant_id=x_tenant_id or settings.default_tenant_id,
        roles=roles,
    )
