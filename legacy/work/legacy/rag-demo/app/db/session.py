from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

try:
    import psycopg
except ImportError:  # pragma: no cover - optional until pgvector backend is used.
    psycopg = None  # type: ignore[assignment]


def database_url() -> str:
    return os.getenv("DATABASE_URL", "").replace("postgresql+psycopg://", "postgresql://", 1)


def psycopg_available() -> bool:
    return psycopg is not None


@contextmanager
def pg_connection() -> Iterator[Any]:
    if psycopg is None:
        raise RuntimeError("psycopg is not installed")
    url = database_url()
    if not url:
        raise RuntimeError("DATABASE_URL is not configured")
    with psycopg.connect(url) as conn:
        yield conn


def can_connect() -> tuple[bool, str]:
    if psycopg is None:
        return False, "psycopg is not installed"
    if not database_url():
        return False, "DATABASE_URL is not configured"
    try:
        with pg_connection() as conn:
            conn.execute("SELECT 1")
        return True, ""
    except Exception as exc:  # noqa: BLE001 - surfaced as pytest skip reason.
        return False, str(exc)
