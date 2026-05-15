from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from app.core.config import PROJECT_ROOT, settings


SECRET_KEYWORDS = (
    "api_key",
    "apikey",
    "authorization",
    "password",
    "passwd",
    "secret",
    "token",
    "x-api-key",
    "llm_api_key",
    "rag_api_key",
)

UNSAFE_PATTERNS = (
    ".env",
    "api key",
    "apikey",
    "token",
    "password",
    "secret",
    "密钥",
    "口令",
    "凭证",
    "读取环境变量",
    "读取 .env",
    "执行 shell",
    "运行 shell",
    "删除文件",
    "发给我",
)


def redact_secrets(value: Any) -> Any:
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            lowered = str(key).lower()
            if any(word in lowered for word in SECRET_KEYWORDS):
                redacted[key] = "***REDACTED***"
            else:
                redacted[key] = redact_secrets(item)
        return redacted
    if isinstance(value, list):
        return [redact_secrets(item) for item in value]
    if isinstance(value, str):
        value = re.sub(
            r"(?i)(api[_-]?key|token|password|secret)\s*[:=]\s*['\"]?[^,\s'\"]+",
            r"\1=***REDACTED***",
            value,
        )
    return value


def is_unsafe_request(user_input: str) -> bool:
    text = user_input.lower()
    if ".env" in text:
        return True
    return any(pattern in text for pattern in UNSAFE_PATTERNS)


def ensure_inside_project(path: Path) -> Path:
    resolved = path.resolve()
    root = PROJECT_ROOT.resolve()
    if resolved != root and root not in resolved.parents:
        raise PermissionError("不允许访问项目目录外的文件")
    if resolved.name == ".env":
        raise PermissionError("不允许读取 .env 文件")
    return resolved


def ensure_inside_finance_dir(path: Path) -> Path:
    resolved = ensure_inside_project(path)
    finance_dir = settings.finance_dir
    if resolved != finance_dir and finance_dir not in resolved.parents:
        raise PermissionError("CSV 工具只能访问 data/finance/ 目录")
    if resolved.name == ".env":
        raise PermissionError("不允许读取 .env 文件")
    return resolved

