from __future__ import annotations

import json
import os
import random
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from rag_core.core.config import AGENT_CORE_ROOT
from rag_core.rag.settings import env_float


def new_trace_id() -> str:
    return str(uuid.uuid4())


def trace_root() -> Path:
    raw = os.getenv("TRACE_STORAGE_DIR")
    if raw:
        path = Path(raw)
        return path if path.is_absolute() else AGENT_CORE_ROOT / path
    return AGENT_CORE_ROOT / "storage" / "traces"


def write_trace(kind: str, payload: dict[str, Any], trace_id: str | None = None) -> Path | None:
    sample_rate = env_float("TRACE_SAMPLE_RATE", 1.0)
    if sample_rate < 1.0 and random.random() > sample_rate:
        return None
    trace_id = trace_id or str(payload.get("trace_id") or new_trace_id())
    payload = {"trace_id": trace_id, "created_at": datetime.now(timezone.utc).isoformat(), **payload}
    directory = trace_root() / kind
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{trace_id}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


