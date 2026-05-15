from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path


PROJECT_ROOT = Path(os.getenv("PLATFORM_ROOT") or Path(__file__).resolve().parents[4])


def _read_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def resolve_project_path(path_value: str) -> Path:
    path = Path(path_value)
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path


def sqlite_path_from_url(database_url: str) -> Path:
    if database_url.startswith("sqlite:///"):
        raw_path = database_url.removeprefix("sqlite:///")
    else:
        raw_path = database_url
    return resolve_project_path(raw_path)


@dataclass(frozen=True)
class Settings:
    app_env: str = field(default_factory=lambda: os.getenv("APP_ENV", "dev"))
    api_key: str = field(default_factory=lambda: os.getenv("API_KEY", "change-me"))
    llm_base_url: str = field(default_factory=lambda: os.getenv("LLM_BASE_URL", ""))
    llm_api_key: str = field(default_factory=lambda: os.getenv("LLM_API_KEY", ""))
    llm_model: str = field(default_factory=lambda: os.getenv("LLM_MODEL", ""))
    structured_data_connector: str = field(default_factory=lambda: os.getenv("STRUCTURED_DATA_CONNECTOR", "sqlite_demo"))
    warehouse_readonly_url: str = field(default_factory=lambda: os.getenv("WAREHOUSE_READONLY_URL", ""))
    database_url: str = field(
        default_factory=lambda: os.getenv(
            "ANALYST_DATABASE_URL",
            os.getenv("DATABASE_URL", "sqlite:///storage/analyst/analyst.db"),
        )
    )
    trace_store_path: str = field(
        default_factory=lambda: os.getenv("ANALYST_INTERNAL_TRACE_PATH", "storage/traces/analyst_internal.jsonl")
    )
    chart_output_dir: str = field(
        default_factory=lambda: os.getenv("ANALYST_CHART_DIR", "storage/analyst/charts")
    )
    max_result_rows: int = field(default_factory=lambda: _read_int("MAX_RESULT_ROWS", 100))
    sql_timeout_seconds: int = field(default_factory=lambda: _read_int("SQL_TIMEOUT_SECONDS", 5))

    @property
    def database_path(self) -> Path:
        return sqlite_path_from_url(self.database_url)

    @property
    def trace_path(self) -> Path:
        return resolve_project_path(self.trace_store_path)

    @property
    def chart_dir(self) -> Path:
        return resolve_project_path(self.chart_output_dir)

    @property
    def llm_enabled(self) -> bool:
        return bool(self.llm_base_url and self.llm_api_key and self.llm_model)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
