from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


ROOT_DIR = Path(os.getenv("PLATFORM_ROOT") or Path(__file__).resolve().parents[3])


def _env(name: str, default: str) -> str:
    value = os.getenv(name)
    return value if value not in (None, "") else default


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw in (None, ""):
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def resolve_in_root(value: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = ROOT_DIR / path
    return path.resolve()


@dataclass(frozen=True)
class PlatformSettings:
    app_env: str = _env("APP_ENV", "dev")
    api_name: str = _env("API_NAME", "Unified AI Workflow Platform")
    demo_mode: bool = _env_bool("DEMO_MODE", True)
    api_host: str = _env("API_HOST", "127.0.0.1")
    api_port: int = _env_int("API_PORT", 8000)
    auth_enabled: bool = _env_bool("AUTH_ENABLED", True)
    api_key: str = _env("API_KEY", "change-me")
    default_user_id: str = _env("DEFAULT_USER_ID", "demo-user")
    default_tenant_id: str = _env("DEFAULT_TENANT_ID", "demo")
    default_roles_raw: str = _env(
        "DEFAULT_ROLES",
        "employee,support,finance,ops,legal,analyst,manager",
    )
    unified_trace_path_value: str = _env("UNIFIED_TRACE_PATH", "storage/traces/runs.jsonl")
    rag_storage_dir_value: str = _env("RAG_STORAGE_DIR", "storage/rag")
    trace_storage_dir_value: str = _env("TRACE_STORAGE_DIR", "storage/traces")
    analyst_database_url: str = _env("ANALYST_DATABASE_URL", "sqlite:///storage/analyst/analyst.db")
    analyst_chart_dir_value: str = _env("ANALYST_CHART_DIR", "storage/analyst/charts")
    analyst_internal_trace_path_value: str = _env(
        "ANALYST_INTERNAL_TRACE_PATH",
        "storage/traces/analyst_internal.jsonl",
    )
    finance_csv_path_value: str = _env("FINANCE_CSV_PATH", "data/finance/financial_metrics.csv")
    ticket_store_path_value: str = _env("TICKET_STORE_PATH", "storage/tickets/tickets.jsonl")
    workflow_internal_trace_path_value: str = _env(
        "WORKFLOW_INTERNAL_TRACE_PATH",
        "storage/traces/workflow_internal.jsonl",
    )
    max_steps_default: int = _env_int("MAX_STEPS_DEFAULT", 6)
    max_result_rows: int = _env_int("MAX_RESULT_ROWS", 100)
    sql_timeout_seconds: int = _env_int("SQL_TIMEOUT_SECONDS", 5)
    request_timeout_seconds: int = _env_int("REQUEST_TIMEOUT_SECONDS", 10)
    retrieval_mode: str = _env("RETRIEVAL_MODE", "hybrid")
    rate_limit_enabled: bool = _env_bool("RATE_LIMIT_ENABLED", True)
    requests_per_minute: int = _env_int("REQUESTS_PER_MINUTE", 120)
    token_budget_per_minute: int = _env_int("TOKEN_BUDGET_PER_MINUTE", 120000)
    event_log_path_value: str = _env("EVENT_LOG_PATH", "storage/traces/events.jsonl")

    @property
    def default_roles(self) -> list[str]:
        return [item.strip() for item in self.default_roles_raw.split(",") if item.strip()]

    @property
    def unified_trace_path(self) -> Path:
        return resolve_in_root(self.unified_trace_path_value)

    @property
    def rag_storage_dir(self) -> Path:
        return resolve_in_root(self.rag_storage_dir_value)

    @property
    def trace_storage_dir(self) -> Path:
        return resolve_in_root(self.trace_storage_dir_value)

    @property
    def analyst_chart_dir(self) -> Path:
        return resolve_in_root(self.analyst_chart_dir_value)

    @property
    def analyst_internal_trace_path(self) -> Path:
        return resolve_in_root(self.analyst_internal_trace_path_value)

    @property
    def finance_csv_path(self) -> Path:
        return resolve_in_root(self.finance_csv_path_value)

    @property
    def ticket_store_path(self) -> Path:
        return resolve_in_root(self.ticket_store_path_value)

    @property
    def workflow_internal_trace_path(self) -> Path:
        return resolve_in_root(self.workflow_internal_trace_path_value)

    @property
    def event_log_path(self) -> Path:
        return resolve_in_root(self.event_log_path_value)


@lru_cache(maxsize=1)
def get_settings() -> PlatformSettings:
    return PlatformSettings()
