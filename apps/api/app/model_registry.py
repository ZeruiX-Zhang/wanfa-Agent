"""Unified Model Registry for Reality OS.

Provides a single configuration surface for all model API connections.
Users configure model "slots" (generator, verifier, classifier, etc.) via
the /settings page, and all system components read from this registry.

Supports any OpenAI-compatible API endpoint, which covers:
- OpenAI (GPT-4o, GPT-4o-mini, o1, etc.)
- Anthropic (via proxy or native)
- Google Gemini (via OpenAI-compatible endpoint)
- DeepSeek
- Groq
- Mistral
- Together AI
- Local Ollama
- Any other OpenAI-compatible provider

Design principles:
- Slots are named roles (generator, verifier, classifier, embedder)
- Each slot has: provider_label, base_url, api_key, model_name, enabled
- API keys are only obfuscated-at-rest (base64 for now, upgrade to Fernet or
  an external secret manager before production)
- The registry is a singleton backed by the same SQLite as knowledge_core
- All reads are from memory cache; writes flush to DB
- Graceful degradation: if a slot is not configured, callers get None
"""

from __future__ import annotations

import base64
import json
import sqlite3
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

from .knowledge_core import get_core


# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

ModelSlot = Literal["generator", "verifier", "classifier", "embedder"]

KNOWN_PROVIDERS = [
    {"id": "openai", "label": "OpenAI", "base_url_hint": "https://api.openai.com/v1", "models_hint": "gpt-4.1, gpt-4.1-mini, gpt-4.1-nano, o3, o4-mini"},
    {"id": "anthropic", "label": "Anthropic (Claude)", "base_url_hint": "https://api.anthropic.com/v1", "models_hint": "claude-opus-4-7, claude-sonnet-4-6, claude-haiku-4"},
    {"id": "gemini", "label": "Google Gemini", "base_url_hint": "https://generativelanguage.googleapis.com/v1beta/openai", "models_hint": "gemini-3-pro, gemini-3-flash, gemini-2.5-pro"},
    {"id": "deepseek", "label": "DeepSeek", "base_url_hint": "https://api.deepseek.com", "models_hint": "deepseek-v4-pro, deepseek-v4-flash"},
    {"id": "groq", "label": "Groq", "base_url_hint": "https://api.groq.com/openai/v1", "models_hint": "llama-4-scout, llama-4-maverick, qwen3-32b"},
    {"id": "mistral", "label": "Mistral", "base_url_hint": "https://api.mistral.ai/v1", "models_hint": "mistral-large-latest, mistral-small-latest"},
    {"id": "xai", "label": "xAI (Grok)", "base_url_hint": "https://api.x.ai/v1", "models_hint": "grok-4, grok-3"},
    {"id": "together", "label": "Together AI", "base_url_hint": "https://api.together.xyz/v1", "models_hint": "meta-llama/Llama-4-Maverick, Qwen/Qwen3-235B"},
    {"id": "ollama", "label": "Ollama (本地)", "base_url_hint": "http://localhost:11434/v1", "models_hint": "qwen3:32b, llama4, deepseek-v4-flash"},
    {"id": "custom", "label": "自定义 / Custom", "base_url_hint": "", "models_hint": ""},
]


@dataclass
class ModelConfig:
    """Configuration for a single model slot."""
    slot: ModelSlot
    provider_id: str  # one of KNOWN_PROVIDERS[*].id
    base_url: str
    api_key: str  # stored obfuscated in DB, plain in memory
    model_name: str
    enabled: bool = True
    display_label: str = ""  # user-friendly label like "GPT-4o for verification"

    def to_dict(self, *, mask_key: bool = True) -> dict[str, Any]:
        return {
            "slot": self.slot,
            "provider_id": self.provider_id,
            "base_url": self.base_url,
            "api_key_configured": bool(self.api_key),
            "api_key_preview": (self.api_key[:4] + "..." + self.api_key[-4:]) if mask_key and len(self.api_key) > 8 else ("***" if self.api_key else ""),
            "model_name": self.model_name,
            "enabled": self.enabled,
            "display_label": self.display_label,
        }


@dataclass
class ModelCallResult:
    ok: bool
    content: str | None
    slot: ModelSlot
    provider_id: str | None
    model_name: str | None
    status: str
    error_type: str | None = None
    error: str | None = None
    retry_count: int = 0
    fallback_used: bool = False
    fallback_from: str | None = None
    latency_ms: int | None = None
    cost_estimate: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "content": self.content,
            "slot": self.slot,
            "provider_id": self.provider_id,
            "model_name": self.model_name,
            "status": self.status,
            "error_type": self.error_type,
            "error": self.error,
            "retry_count": self.retry_count,
            "fallback_used": self.fallback_used,
            "fallback_from": self.fallback_from,
            "latency_ms": self.latency_ms,
            "cost_estimate": self.cost_estimate,
        }


# ---------------------------------------------------------------------------
# Registry (singleton, thread-safe)
# ---------------------------------------------------------------------------


class ModelRegistry:
    """In-memory + SQLite-backed model configuration registry."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._cache: dict[str, ModelConfig] = {}  # slot -> config
        self._ensure_schema()
        self._load_from_db()

    def _get_db(self) -> sqlite3.Connection:
        core = get_core()
        conn = sqlite3.connect(core.path)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self) -> None:
        with self._get_db() as db:
            db.execute("""
                create table if not exists model_registry (
                    slot text primary key,
                    provider_id text not null,
                    base_url text not null,
                    api_key_enc text not null default '',
                    model_name text not null,
                    enabled integer not null default 1,
                    display_label text not null default ''
                )
            """)

    def _load_from_db(self) -> None:
        with self._get_db() as db:
            rows = db.execute("select * from model_registry").fetchall()
        with self._lock:
            self._cache.clear()
            for row in rows:
                self._cache[row["slot"]] = ModelConfig(
                    slot=row["slot"],
                    provider_id=row["provider_id"],
                    base_url=row["base_url"],
                    api_key=_decode_key(row["api_key_enc"]),
                    model_name=row["model_name"],
                    enabled=bool(row["enabled"]),
                    display_label=row["display_label"] or "",
                )

    def get(self, slot: ModelSlot) -> ModelConfig | None:
        """Get config for a slot. Returns None if not configured or disabled."""
        with self._lock:
            config = self._cache.get(slot)
            if config and config.enabled:
                return config
            return None

    def get_all(self) -> list[ModelConfig]:
        """Get all configured slots."""
        with self._lock:
            return list(self._cache.values())

    def set(self, config: ModelConfig) -> ModelConfig:
        """Create or update a model slot configuration."""
        with self._lock:
            existing = self._cache.get(config.slot)
            if existing and not config.api_key:
                config.api_key = existing.api_key
            self._cache[config.slot] = config
        with self._get_db() as db:
            db.execute("""
                insert into model_registry(slot, provider_id, base_url, api_key_enc, model_name, enabled, display_label)
                values(?, ?, ?, ?, ?, ?, ?)
                on conflict(slot) do update set
                    provider_id = excluded.provider_id,
                    base_url = excluded.base_url,
                    api_key_enc = excluded.api_key_enc,
                    model_name = excluded.model_name,
                    enabled = excluded.enabled,
                    display_label = excluded.display_label
            """, (
                config.slot,
                config.provider_id,
                config.base_url,
                _encode_key(config.api_key),
                config.model_name,
                1 if config.enabled else 0,
                config.display_label,
            ))
        return config

    def delete(self, slot: ModelSlot) -> bool:
        """Remove a slot configuration."""
        with self._lock:
            removed = self._cache.pop(slot, None)
        if removed:
            with self._get_db() as db:
                db.execute("delete from model_registry where slot = ?", (slot,))
            return True
        return False

    def test_connection(self, slot: ModelSlot) -> dict[str, Any]:
        """Test connectivity to a configured model slot."""
        config = self.get(slot)
        if not config:
            return {"ok": False, "error": f"Slot '{slot}' is not configured or disabled."}
        return _test_model_connection(config)


# ---------------------------------------------------------------------------
# Model invocation helper
# ---------------------------------------------------------------------------


def call_model(
    slot: ModelSlot,
    *,
    prompt: str,
    system: str = "",
    temperature: float = 0.0,
    max_tokens: int = 1000,
    timeout: int = 15,
    retries: int = 0,
    fallback_slots: list[ModelSlot] | None = None,
    return_result: bool = False,
    run_id: str | None = None,
    step_id: str | None = None,
) -> str | None | ModelCallResult:
    """Call a model by slot name.

    This is the unified entry point for all LLM calls in Reality OS.

    Backward compatibility: by default this returns ``str | None`` exactly as
    older callers expect. Set ``return_result=True`` to receive a structured
    ``ModelCallResult`` with error type, retry count, fallback metadata, and
    rough cost estimate.
    """
    result = _call_model_result(
        slot,
        prompt=prompt,
        system=system,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=timeout,
        retries=max(0, retries),
        fallback_slots=fallback_slots or [],
        run_id=run_id,
        step_id=step_id,
    )
    if return_result:
        return result
    return result.content if result.ok else None


def _call_model_result(
    slot: ModelSlot,
    *,
    prompt: str,
    system: str,
    temperature: float,
    max_tokens: int,
    timeout: int,
    retries: int,
    fallback_slots: list[ModelSlot],
    run_id: str | None,
    step_id: str | None,
) -> ModelCallResult:
    registry = get_registry()
    slots: list[ModelSlot] = [slot, *fallback_slots]
    last_result: ModelCallResult | None = None

    for index, candidate_slot in enumerate(slots):
        config = registry.get(candidate_slot)
        fallback_used = index > 0
        fallback_from = slots[index - 1] if fallback_used else None

        if not config:
            last_result = ModelCallResult(
                ok=False,
                content=None,
                slot=candidate_slot,
                provider_id=None,
                model_name=None,
                status="not_configured",
                error_type="not_configured",
                error=f"Slot '{candidate_slot}' is not configured or disabled.",
                fallback_used=fallback_used,
                fallback_from=fallback_from,
            )
            _record_model_trace(
                result=last_result,
                run_id=run_id,
                step_id=step_id,
                started_at=_now(),
                ended_at=_now(),
                input_value={"prompt": prompt, "system": system},
                output_value=None,
                timeout=timeout,
            )
            continue

        if not config.api_key and config.provider_id != "ollama":
            last_result = ModelCallResult(
                ok=False,
                content=None,
                slot=candidate_slot,
                provider_id=config.provider_id,
                model_name=config.model_name,
                status="missing_api_key",
                error_type="missing_api_key",
                error=f"Slot '{candidate_slot}' has no API key configured.",
                fallback_used=fallback_used,
                fallback_from=fallback_from,
            )
            _record_model_trace(
                result=last_result,
                run_id=run_id,
                step_id=step_id,
                started_at=_now(),
                ended_at=_now(),
                input_value={"prompt": prompt, "system": system},
                output_value=None,
                timeout=timeout,
            )
            continue

        for attempt in range(retries + 1):
            started_at = _now()
            started_perf = time.perf_counter()
            try:
                content = _call_openai_compatible(
                    config,
                    prompt=prompt,
                    system=system,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    timeout=timeout,
                )
                latency_ms = int((time.perf_counter() - started_perf) * 1000)
                result = ModelCallResult(
                    ok=bool(content),
                    content=content,
                    slot=candidate_slot,
                    provider_id=config.provider_id,
                    model_name=config.model_name,
                    status="completed" if content else "empty_response",
                    error_type=None if content else "empty_response",
                    error=None if content else "Provider returned no message content.",
                    retry_count=attempt,
                    fallback_used=fallback_used,
                    fallback_from=fallback_from,
                    latency_ms=latency_ms,
                    cost_estimate=_estimate_cost(prompt, system, max_tokens),
                )
                _record_model_trace(
                    result=result,
                    run_id=run_id,
                    step_id=step_id,
                    started_at=started_at,
                    ended_at=_now(),
                    input_value={"prompt": prompt, "system": system},
                    output_value=content,
                    timeout=timeout,
                )
                if result.ok:
                    return result
                last_result = result
                break
            except Exception as exc:
                latency_ms = int((time.perf_counter() - started_perf) * 1000)
                error_type = _classify_error(exc)
                transient = error_type in {"timeout", "network", "rate_limited", "http_5xx"}
                if attempt < retries and transient:
                    last_result = ModelCallResult(
                        ok=False,
                        content=None,
                        slot=candidate_slot,
                        provider_id=config.provider_id,
                        model_name=config.model_name,
                        status="retrying",
                        error_type=error_type,
                        error=str(exc)[:300],
                        retry_count=attempt + 1,
                        fallback_used=fallback_used,
                        fallback_from=fallback_from,
                        latency_ms=latency_ms,
                        cost_estimate=_estimate_cost(prompt, system, max_tokens),
                    )
                    continue

                last_result = ModelCallResult(
                    ok=False,
                    content=None,
                    slot=candidate_slot,
                    provider_id=config.provider_id,
                    model_name=config.model_name,
                    status="failed",
                    error_type=error_type,
                    error=str(exc)[:300],
                    retry_count=attempt,
                    fallback_used=fallback_used,
                    fallback_from=fallback_from,
                    latency_ms=latency_ms,
                    cost_estimate=_estimate_cost(prompt, system, max_tokens),
                )
                _record_model_trace(
                    result=last_result,
                    run_id=run_id,
                    step_id=step_id,
                    started_at=started_at,
                    ended_at=_now(),
                    input_value={"prompt": prompt, "system": system},
                    output_value=None,
                    timeout=timeout,
                )
                break

    return last_result or ModelCallResult(
        ok=False,
        content=None,
        slot=slot,
        provider_id=None,
        model_name=None,
        status="not_configured",
        error_type="not_configured",
        error=f"Slot '{slot}' is not configured or disabled.",
    )


def _call_openai_compatible(
    config: ModelConfig,
    *,
    prompt: str,
    system: str,
    temperature: float,
    max_tokens: int,
    timeout: int,
) -> str | None:
    messages: list[dict[str, str]] = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    headers = {"Content-Type": "application/json"}
    if config.api_key:
        headers["Authorization"] = f"Bearer {config.api_key}"
    payload = json.dumps({
        "model": config.model_name,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{config.base_url.rstrip('/')}/chat/completions",
        data=payload,
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        result = json.loads(resp.read().decode("utf-8"))

    content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
    return content.strip() if content else None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _classify_error(exc: Exception) -> str:
    if isinstance(exc, TimeoutError):
        return "timeout"
    if isinstance(exc, urllib.error.HTTPError):
        if exc.code == 401 or exc.code == 403:
            return "auth"
        if exc.code == 429:
            return "rate_limited"
        if exc.code >= 500:
            return "http_5xx"
        return "http_error"
    if isinstance(exc, urllib.error.URLError):
        reason = getattr(exc, "reason", None)
        if isinstance(reason, TimeoutError):
            return "timeout"
        return "network"
    if isinstance(exc, json.JSONDecodeError):
        return "invalid_json"
    return "unknown"


def _estimate_cost(prompt: str, system: str, max_tokens: int) -> float | None:
    """Return a provider-neutral rough cost unit, not a billed USD value."""

    input_tokens = max(1, int((len(prompt) + len(system)) / 4))
    estimated_tokens = input_tokens + max(0, max_tokens)
    return round(estimated_tokens / 1000, 4)


def _record_model_trace(
    *,
    result: ModelCallResult,
    run_id: str | None,
    step_id: str | None,
    started_at: str,
    ended_at: str,
    input_value: Any,
    output_value: Any,
    timeout: int,
) -> None:
    try:
        from .trace import record_model_call

        record_model_call(
            run_id=run_id,
            step_id=step_id,
            slot=result.slot,
            provider_id=result.provider_id,
            model_name=result.model_name,
            status=result.status,
            started_at=started_at,
            ended_at=ended_at,
            latency_ms=result.latency_ms,
            input_value=input_value,
            output_value=output_value,
            error_type=result.error_type,
            error=result.error,
            retry_count=result.retry_count,
            fallback_from=result.fallback_from,
            fallback_used=result.fallback_used,
            cost_estimate=result.cost_estimate,
            timeout_seconds=timeout,
        )
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Connection test
# ---------------------------------------------------------------------------


def _test_model_connection(config: ModelConfig) -> dict[str, Any]:
    """Send a minimal request to verify the model endpoint is reachable."""
    if not config.api_key and config.provider_id != "ollama":
        return {
            "ok": False,
            "error": "API key is missing for this provider.",
            "error_type": "missing_api_key",
            "health_status": "unhealthy",
            "model": config.model_name,
            "provider": config.provider_id,
        }
    try:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {config.api_key}",
        }
        payload = json.dumps({
            "model": config.model_name,
            "messages": [{"role": "user", "content": "Reply with OK"}],
            "temperature": 0.0,
            "max_tokens": 5,
        }).encode("utf-8")

        req = urllib.request.Request(
            f"{config.base_url.rstrip('/')}/chat/completions",
            data=payload,
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read().decode("utf-8"))

        content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
        return {
            "ok": True,
            "response": content.strip()[:50],
            "model": config.model_name,
            "provider": config.provider_id,
            "health_status": "healthy",
        }
    except Exception as exc:
        return {
            "ok": False,
            "error": str(exc)[:200],
            "error_type": _classify_error(exc),
            "health_status": "unhealthy",
            "model": config.model_name,
            "provider": config.provider_id,
        }


# ---------------------------------------------------------------------------
# Key obfuscation (base64 — upgrade to Fernet for production)
# ---------------------------------------------------------------------------


def _encode_key(key: str) -> str:
    if not key:
        return ""
    return base64.b64encode(key.encode("utf-8")).decode("ascii")


def _decode_key(encoded: str) -> str:
    if not encoded:
        return ""
    try:
        return base64.b64decode(encoded.encode("ascii")).decode("utf-8")
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_REGISTRY: ModelRegistry | None = None


def get_registry() -> ModelRegistry:
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = ModelRegistry()
    return _REGISTRY


def reset_registry_for_tests() -> ModelRegistry:
    global _REGISTRY
    _REGISTRY = ModelRegistry()
    return _REGISTRY
