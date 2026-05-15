from __future__ import annotations

from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader

from app.core.config import get_settings
from app.schemas.data_agent import ErrorResponse


api_key_header = APIKeyHeader(name="x-api-key", auto_error=False)


async def require_api_key(api_key: str | None = Security(api_key_header)) -> None:
    settings = get_settings()
    if not settings.api_key:
        return
    if api_key != settings.api_key:
        detail = ErrorResponse(
            code="unauthorized",
            message="缺少或无效的 API Key，请在 x-api-key 请求头中传入正确值。",
        ).model_dump()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)

