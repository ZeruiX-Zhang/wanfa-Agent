from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

from platform_common.models import UnifiedRunTrace, utc_now
from platform_common.settings import PlatformSettings, get_settings


def new_trace_id(prefix: str = "trace") -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


class UnifiedTraceStore:
    def __init__(self, settings: PlatformSettings | None = None, path: Path | None = None) -> None:
        self.settings = settings or get_settings()
        self.path = path or self.settings.unified_trace_path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def list_runs(self) -> list[UnifiedRunTrace]:
        if not self.path.exists():
            return []
        runs: list[UnifiedRunTrace] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                runs.append(UnifiedRunTrace.model_validate(json.loads(line)))
        return runs

    def get(self, run_id: str) -> UnifiedRunTrace | None:
        for run in self.list_runs():
            if run.run_id == run_id:
                return run
        return None

    def save(self, trace: UnifiedRunTrace) -> None:
        trace.updated_at = utc_now()
        traces = [item for item in self.list_runs() if item.run_id != trace.run_id]
        traces.append(trace)
        payload = "\n".join(json.dumps(item.model_dump(mode="json"), ensure_ascii=False) for item in traces)
        self.path.write_text(payload + ("\n" if payload else ""), encoding="utf-8")
