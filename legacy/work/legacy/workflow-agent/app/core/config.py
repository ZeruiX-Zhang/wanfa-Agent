from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _env(name: str, default: str) -> str:
    value = os.getenv(name)
    return value if value not in (None, "") else default


def resolve_project_path(value: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    resolved = path.resolve()
    root = PROJECT_ROOT.resolve()
    if resolved != root and root not in resolved.parents:
        raise ValueError(f"path must stay inside project root: {value}")
    return resolved


@dataclass(frozen=True)
class Settings:
    app_env: str = _env("APP_ENV", "dev")
    api_key: str = _env("API_KEY", "change-me")
    llm_base_url: str = _env("LLM_BASE_URL", "")
    llm_api_key: str = _env("LLM_API_KEY", "")
    llm_model: str = _env("LLM_MODEL", "")
    rag_base_url: str = _env("RAG_BASE_URL", "http://127.0.0.1:8765")
    rag_api_key: str = _env("RAG_API_KEY", "change-me")
    trace_store_path: str = _env("TRACE_STORE_PATH", "data/traces/runs.jsonl")
    ticket_store_path: str = _env("TICKET_STORE_PATH", "data/tickets/tickets.jsonl")
    finance_csv_path: str = _env("FINANCE_CSV_PATH", "data/finance/financial_metrics.csv")
    max_steps_default: int = int(_env("MAX_STEPS_DEFAULT", "6"))
    request_timeout_seconds: float = float(_env("REQUEST_TIMEOUT_SECONDS", "5"))

    @property
    def trace_path(self) -> Path:
        return resolve_project_path(self.trace_store_path)

    @property
    def ticket_path(self) -> Path:
        return resolve_project_path(self.ticket_store_path)

    @property
    def finance_csv(self) -> Path:
        return resolve_project_path(self.finance_csv_path)

    @property
    def finance_dir(self) -> Path:
        return (PROJECT_ROOT / "data" / "finance").resolve()


settings = Settings()

