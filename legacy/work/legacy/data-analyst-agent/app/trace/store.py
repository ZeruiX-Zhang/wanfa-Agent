from __future__ import annotations

import json

from app.core.config import Settings, get_settings
from app.schemas.data_agent import DataAgentTrace
from app.security.redaction import redact_obj


class TraceStore:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()

    def append(self, trace: DataAgentTrace) -> None:
        trace_path = self.settings.trace_path
        trace_path.parent.mkdir(parents=True, exist_ok=True)
        payload = trace.model_dump(mode="json")
        payload = redact_obj(payload)
        with trace_path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(payload, ensure_ascii=False) + "\n")

    def get(self, run_id: str) -> DataAgentTrace | None:
        trace_path = self.settings.trace_path
        if not trace_path.exists():
            return None
        with trace_path.open("r", encoding="utf-8") as file:
            for line in file:
                if not line.strip():
                    continue
                payload = json.loads(line)
                if payload.get("run_id") == run_id:
                    return DataAgentTrace.model_validate(payload)
        return None

