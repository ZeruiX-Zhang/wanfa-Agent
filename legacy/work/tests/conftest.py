from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


ROOT_DIR = Path(__file__).resolve().parents[1]
os.environ.setdefault("PLATFORM_ROOT", str(ROOT_DIR))
os.environ.setdefault("API_KEY", "change-me")
os.environ.setdefault("AUTH_ENABLED", "true")

import sitecustomize  # noqa: F401
from api.main import app
from scripts.init_platform import initialize_platform


@pytest.fixture(scope="session", autouse=True)
def setup_demo_state() -> None:
    initialize_platform(reset_traces=True)


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)
