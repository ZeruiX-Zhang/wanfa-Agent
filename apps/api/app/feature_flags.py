"""Feature-flag and tunable reader for the ``expert-coaching-loop`` feature.

Centralises every environment-variable lookup added by the spec so the rest
of the codebase can call typed helpers instead of probing ``os.environ`` ad
hoc. This keeps the dark-launch matrix predictable and gives every flag a
single, audited entry point (R15.2, R18.1).

All flags default to *off* / *disabled* so deploying this module changes no
runtime behaviour until an operator explicitly flips a flag (R11, R15).
"""

from __future__ import annotations

import os
from typing import Literal

EmbedMode = Literal["online", "offline", "disabled"]


_TRUTHY = {"1", "true", "yes", "on", "y", "t"}
_FALSY = {"0", "false", "no", "off", "n", "f", ""}


def _bool(name: str, default: bool = False) -> bool:
    """Read a boolean flag from the environment.

    Unknown values fall back to ``default`` (no exception) so a typo cannot
    silently disable safety-critical features.
    """

    raw = os.getenv(name)
    if raw is None:
        return default
    value = raw.strip().lower()
    if value in _TRUTHY:
        return True
    if value in _FALSY:
        return False
    return default


def _float(name: str, default: float, *, low: float, high: float) -> float:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    if value < low or value > high:
        return default
    return value


def _int(name: str, default: int, *, low: int, high: int) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    if value < low or value > high:
        return default
    return value


# ---- Boolean dark-launch flags ------------------------------------------


def coach_enabled() -> bool:
    """``REALITY_OS_COACH_ENABLED`` — gate ``/api/v2/coach/*`` routes (M1+)."""

    return _bool("REALITY_OS_COACH_ENABLED", default=False)


def expert_gap_enabled() -> bool:
    """``REALITY_OS_EXPERT_GAP_ENABLED`` — adds 6th audit dimension (R2.5)."""

    return _bool("REALITY_OS_EXPERT_GAP_ENABLED", default=False)


def hybrid_retrieval_enabled() -> bool:
    """``REALITY_OS_HYBRID_RETRIEVAL`` — switch retrieval to hybrid scorer."""

    return _bool("REALITY_OS_HYBRID_RETRIEVAL", default=False)


def coach_autoswitch() -> bool:
    """``REALITY_OS_COACH_AUTOSWITCH`` — auto-apply skill-chain switches.

    Defaults to ``False`` so Simple_Mode (R3.5) requires explicit user
    confirmation before changing chain.
    """

    return _bool("REALITY_OS_COACH_AUTOSWITCH", default=False)


# ---- Tunables ------------------------------------------------------------


def embed_mode() -> EmbedMode:
    """``REALITY_OS_EMBED_MODE`` ∈ {online, offline, disabled} (R8.5, R8.6)."""

    raw = (os.getenv("REALITY_OS_EMBED_MODE") or "disabled").strip().lower()
    if raw in {"online", "offline", "disabled"}:
        return raw  # type: ignore[return-value]
    return "disabled"


def vector_store() -> str:
    """``REALITY_OS_VECTOR_STORE`` — vector backend selection (R8.5, R18.1)."""

    return (os.getenv("REALITY_OS_VECTOR_STORE") or "sqlite_tfidf").strip().lower()


def coach_idle_days() -> int:
    """``REALITY_OS_COACH_IDLE_DAYS`` — auto-archive threshold (R1.6).

    Bounded to ``[1, 365]`` so a misconfiguration cannot disable archival
    (``0``) or stall it indefinitely (``> 1y``).
    """

    return _int("REALITY_OS_COACH_IDLE_DAYS", default=30, low=1, high=365)


def calibration_threshold() -> float:
    """``REALITY_OS_CALIBRATION_THRESHOLD`` — bias-to-practice cutoff (R4.5).

    Bounded to ``[0.0, 1.0]``.
    """

    return _float(
        "REALITY_OS_CALIBRATION_THRESHOLD", default=0.6, low=0.0, high=1.0
    )


def consecutive_fail_threshold() -> int:
    """``REALITY_OS_CONSECUTIVE_FAIL_THRESHOLD`` — K trailing fails (R3.4, R9.3)."""

    return _int(
        "REALITY_OS_CONSECUTIVE_FAIL_THRESHOLD", default=3, low=1, high=20
    )


# ---- Server-only secrets exposure check (R15.3) -------------------------


SERVER_ONLY_PREFIX = "REALITY_OS_"
SERVER_ONLY_SECRET_NAMES: tuple[str, ...] = (
    "REALITY_OS_API_KEY",
    "REALITY_OS_SERVER_API_KEY",
)
# Env vars Next.js exposes to the browser carry this prefix. Any
# ``REALITY_OS_*`` server secret leaking into ``NEXT_PUBLIC_*`` is a
# misconfiguration we must refuse on startup.
CLIENT_BUNDLE_PREFIX = "NEXT_PUBLIC_"


def detect_client_secret_leaks(env: dict[str, str] | None = None) -> list[str]:
    """Return a list of env vars that would leak server secrets to the client.

    A leak is any env var whose key starts with :data:`CLIENT_BUNDLE_PREFIX`
    *and* whose value matches a configured server-only secret. The check is
    structural; it does not echo the secret itself (R15.3, R18.4).
    """

    source = env if env is not None else dict(os.environ)
    server_values: dict[str, str] = {}
    for name in SERVER_ONLY_SECRET_NAMES:
        value = source.get(name)
        if value:
            server_values[name] = value

    leaks: list[str] = []
    if not server_values:
        return leaks

    for key, value in source.items():
        if not key.startswith(CLIENT_BUNDLE_PREFIX):
            continue
        if not value:
            continue
        for secret_name, secret_value in server_values.items():
            if value == secret_value:
                leaks.append(f"{key} mirrors {secret_name}")
                break
    return leaks
