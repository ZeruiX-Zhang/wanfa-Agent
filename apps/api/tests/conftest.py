"""Pytest fixtures for the Reality OS API tests."""

from __future__ import annotations

import os
import tempfile
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="session")
def client() -> Iterator[TestClient]:
    """Return a FastAPI test client with a disposable SQLite storage path."""

    with tempfile.TemporaryDirectory(prefix="reality-os-tests-", ignore_cleanup_errors=True) as tmp_dir:
        storage_path = os.path.join(tmp_dir, "reality_os_test.sqlite3")
        os.environ["REALITY_OS_API_STORAGE"] = storage_path
        os.environ.setdefault("REALITY_OS_ENV", "development")
        os.environ.pop("REALITY_OS_API_AUTH_REQUIRED", None)
        os.environ.pop("REALITY_OS_API_KEY", None)
        os.environ.pop("REALITY_OS_SERVER_API_KEY", None)
        # Coach routes are dark-launched behind ``REALITY_OS_COACH_ENABLED``
        # (Task 2.17). The integration suite exercises the live routes so
        # we flip the flag *on* by default; the dedicated flag test
        # (`test_flag_coach_enabled`) uses ``monkeypatch.setenv`` to
        # toggle it per case.
        os.environ.setdefault("REALITY_OS_COACH_ENABLED", "true")

        # Reset cached singletons so they pick up the temp storage path.
        from apps.api import storage as storage_mod
        from apps.api import main as api_main

        storage_mod._STORAGE = None
        api_main.storage = storage_mod.get_storage()

        from apps.api.main import app

        try:
            with TestClient(app) as instance:
                yield instance
        finally:
            storage_mod._STORAGE = None
