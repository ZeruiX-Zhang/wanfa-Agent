from __future__ import annotations

import json
from pathlib import Path

from app.core.config import settings
from app.schemas.agent import AgentTrace, utc_now
from app.security.policies import redact_secrets


class TraceStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or settings.trace_path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def list_runs(self) -> list[AgentTrace]:
        if not self.path.exists():
            return []
        runs: list[AgentTrace] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                runs.append(AgentTrace.model_validate(json.loads(line)))
        return runs

    def get(self, run_id: str) -> AgentTrace | None:
        for run in self.list_runs():
            if run.run_id == run_id:
                return run
        return None

    def save(self, trace: AgentTrace) -> None:
        trace.updated_at = utc_now()
        safe_payload = redact_secrets(trace.model_dump())
        traces = [run for run in self.list_runs() if run.run_id != trace.run_id]
        traces.append(AgentTrace.model_validate(safe_payload))
        payload = "\n".join(
            json.dumps(run.model_dump(), ensure_ascii=False, default=str) for run in traces
        )
        self.path.write_text(payload + ("\n" if payload else ""), encoding="utf-8")

