from __future__ import annotations

import os
from pathlib import Path

from rag_core.core.config import AGENT_CORE_ROOT


def env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if not value:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if not value:
        return default
    try:
        return float(value)
    except ValueError:
        return default


def env_str(name: str, default: str) -> str:
    return os.getenv(name, default).strip() or default


def rag_storage_dir() -> Path:
    raw = os.getenv("RAG_STORAGE_DIR")
    if raw:
        path = Path(raw)
        return path if path.is_absolute() else AGENT_CORE_ROOT / path
    return AGENT_CORE_ROOT / "storage" / "rag"


