from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from platform_common.settings import get_settings


def log_event(event: dict[str, Any]) -> None:
    settings = get_settings()
    path = settings.event_log_path
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"created_at": datetime.now(timezone.utc).isoformat(), **event}
    with path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(payload, ensure_ascii=False) + "\n")


def list_events(limit: int = 20) -> list[dict[str, Any]]:
    path = get_settings().event_log_path
    if not path.exists():
        return []
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return rows[-limit:][::-1]
