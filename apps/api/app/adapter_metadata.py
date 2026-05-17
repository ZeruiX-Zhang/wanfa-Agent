"""Helpers for emitting :class:`AdapterMetadata` from new endpoints.

Centralised so every new write path declares ``mode`` consistently with
R11.5 (``pending-review`` / ``dry-run`` / ``mock-safe`` / ``read-only``).
"""

from __future__ import annotations

from typing import Literal, get_args

from apps.api.schemas import AdapterMetadata, AdapterMode


# Allowed values for ``AdapterMetadata.mode`` are sourced from the existing
# ``AdapterMode`` literal so this helper stays in lockstep with
# ``apps/api/schemas.py``.
ALLOWED_MODES: frozenset[str] = frozenset(get_args(AdapterMode))


def make_metadata(
    *,
    adapter: str,
    source_system: str,
    mode: Literal["mock-safe", "read-only", "pending-review", "dry-run", "blocked"] = "mock-safe",
    read_only: bool = True,
) -> AdapterMetadata:
    """Build an :class:`AdapterMetadata` after validating ``mode``.

    Parameters
    ----------
    adapter:
        Dotted adapter id (e.g. ``"v2.coach.turn"``).
    source_system:
        The originating system (``"apps:api"`` for in-process logic).
    mode:
        Must be one of :data:`ALLOWED_MODES`. Any other value raises
        :class:`ValueError` so a misuse is caught at call sites instead of
        leaking into clients.
    read_only:
        Mirrors ``AdapterMetadata.read_only``. Default ``True`` keeps the
        safe-by-default contract.
    """

    if mode not in ALLOWED_MODES:
        raise ValueError(
            f"unknown AdapterMetadata.mode: {mode!r}; expected one of {sorted(ALLOWED_MODES)}"
        )
    return AdapterMetadata(
        adapter=adapter,
        source_system=source_system,
        mode=mode,
        read_only=read_only,
    )
