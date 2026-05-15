from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from workflow_core.core.config import PROJECT_ROOT, settings


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
    "凭证",
    "读取环境变量",
    "读取 .env",
    "执行 shell",
    "run shell",
    "delete file",
    "remove file",
)


def redact_secrets(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: "***REDACTED***" if any(word in str(key).lower() for word in SECRET_KEYWORDS) else redact_secrets(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_secrets(item) for item in value]
    if isinstance(value, str):
        return re.sub(
            r"(?i)(api[_-]?key|token|password|secret)\s*[:=]\s*['\"]?[^,\s'\"]+",
            r"\1=***REDACTED***",
            value,
        )
    return value


def is_unsafe_request(user_input: str) -> bool:
    text = user_input.lower()
    return any(pattern in text for pattern in UNSAFE_PATTERNS)


def ensure_inside_project(path: Path) -> Path:
    resolved = path.resolve()
    root = PROJECT_ROOT.resolve()
    if resolved != root and root not in resolved.parents:
        raise PermissionError("Access outside the project root is not allowed.")
    if resolved.name == ".env":
        raise PermissionError("Reading .env is not allowed.")
    return resolved


def ensure_inside_finance_dir(path: Path) -> Path:
    resolved = ensure_inside_project(path)
    finance_dir = settings.finance_dir
    if resolved != finance_dir and finance_dir not in resolved.parents:
        raise PermissionError("CSV access is restricted to the finance data directory.")
    return resolved
