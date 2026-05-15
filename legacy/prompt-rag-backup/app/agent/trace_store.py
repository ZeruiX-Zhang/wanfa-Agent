from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from app.core.config import settings
from app.core.errors import AppError


class TraceStore:
    def __init__(self, storage_dir: Path | None = None) -> None:
        self.storage_dir = storage_dir or settings.project_root / "storage" / "traces"

    def save(self, run_id: str, trace: dict[str, object]) -> None:
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        path = self._path_for(run_id)
        path.write_text(json.dumps(trace, ensure_ascii=False, indent=2), encoding="utf-8")

    def get(self, run_id: str) -> dict[str, object]:
        path = self._path_for(run_id)
        if not path.exists():
            raise AppError(f"Agent run not found: {run_id}", status_code=404, code="run_not_found")
        return json.loads(path.read_text(encoding="utf-8"))

    def _path_for(self, run_id: str) -> Path:
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", run_id):
            raise AppError("Invalid run_id", status_code=400, code="invalid_run_id")
        return self.storage_dir / f"{run_id}.json"

    def now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat()
