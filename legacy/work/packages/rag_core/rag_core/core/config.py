from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - python-dotenv is optional at import time.
    load_dotenv = None


PACKAGE_ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = Path(os.getenv("PLATFORM_ROOT") or Path(__file__).resolve().parents[4])
AGENT_CORE_ROOT = PROJECT_ROOT

if load_dotenv is not None:
    load_dotenv(PROJECT_ROOT / ".env", override=False)


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class AppConfig:
    app_name: str = "RAG Demo"
    host: str = "127.0.0.1"
    port: int = 8000
    auth_enabled: bool = False
    demo_api_key: str = "change-me"


def _load_json_config() -> dict[str, Any]:
    config_path = Path(os.getenv("RAG_DEMO_CONFIG") or PROJECT_ROOT / "config.json")
    if not config_path.exists():
        return {}
    with config_path.open("r", encoding="utf-8") as file:
        return json.load(file)


def load_config() -> AppConfig:
    raw = _load_json_config()
    return AppConfig(
        host=os.getenv("API_HOST", os.getenv("RAG_DEMO_HOST", raw.get("host", "127.0.0.1"))),
        port=int(os.getenv("API_PORT", os.getenv("RAG_DEMO_PORT", raw.get("port", 8000)))),
        auth_enabled=_env_bool("AUTH_ENABLED", bool(raw.get("auth_enabled", False))),
        demo_api_key=os.getenv("API_KEY", os.getenv("DEMO_API_KEY", raw.get("demo_api_key", "change-me"))),
    )


settings = load_config()
