from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.init_db import initialize_database


@pytest.fixture()
def api_key() -> str:
    return "change-me"


@pytest.fixture()
def headers(api_key: str) -> dict[str, str]:
    return {"x-api-key": api_key}


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    database_path = tmp_path / "analyst.db"
    chart_dir = tmp_path / "charts"
    trace_path = tmp_path / "traces" / "runs.jsonl"
    initialize_database(database_path)
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("API_KEY", "change-me")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database_path.as_posix()}")
    monkeypatch.setenv("TRACE_STORE_PATH", trace_path.as_posix())
    monkeypatch.setenv("CHART_OUTPUT_DIR", chart_dir.as_posix())
    monkeypatch.setenv("MAX_RESULT_ROWS", "100")
    monkeypatch.setenv("SQL_TIMEOUT_SECONDS", "5")

    from app.core.config import get_settings

    get_settings.cache_clear()
    from app.main import app

    with TestClient(app) as test_client:
        yield test_client
    get_settings.cache_clear()

