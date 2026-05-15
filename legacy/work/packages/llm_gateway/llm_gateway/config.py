from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml


ROOT_DIR = Path(os.getenv("PLATFORM_ROOT") or Path(__file__).resolve().parents[3])


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as file:
        data = yaml.safe_load(file) or {}
    return data if isinstance(data, dict) else {}


@lru_cache(maxsize=1)
def model_config() -> dict[str, Any]:
    return _read_yaml(ROOT_DIR / "configs" / "models.yaml")


def resolve_model(model_name: str | None, operation: str) -> tuple[str, dict[str, Any], dict[str, Any]]:
    config = model_config()
    default_key = {
        "chat": "default_chat_model",
        "structured_output": "default_chat_model",
        "tool_call": "default_chat_model",
        "embedding": "default_embedding_model",
        "rerank": "default_reranker_model",
    }.get(operation, "default_chat_model")
    env_key = {
        "default_chat_model": "DEFAULT_CHAT_MODEL",
        "default_embedding_model": "DEFAULT_EMBEDDING_MODEL",
        "default_reranker_model": "DEFAULT_RERANKER_MODEL",
    }.get(default_key)
    selected = model_name or (os.getenv(env_key) if env_key else None) or str(config.get(default_key) or "mock-chat")
    model_entry = dict((config.get("models") or {}).get(selected) or {})
    provider_name = str(model_entry.get("provider") or "mock")
    provider_entry = dict((config.get("providers") or {}).get(provider_name) or {})
    api_key_env = str(provider_entry.get("api_key_env") or "")
    if provider_name != "mock" and api_key_env and not os.getenv(api_key_env):
        provider_name = "mock"
        provider_entry = dict((config.get("providers") or {}).get("mock") or {})
        selected = str(config.get("default_chat_model") or "mock-chat") if operation != "embedding" else str(config.get("default_embedding_model") or "mock-embedding")
        model_entry = dict((config.get("models") or {}).get(selected) or {})
    return selected, model_entry, {"name": provider_name, **provider_entry}


def prompt_version(default: str = "v1") -> str:
    return str(model_config().get("prompt_version") or default)
