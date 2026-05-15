from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.auth import DEMO_ROLES, require_auth
from app.core.config import settings
from app.main import app
from app.rag.models import Chunk
from app.rag.service import rag_service


client = TestClient(app)
AUTH_HEADERS = {"X-API-Key": "test-key"}


def _seed_demo_support_docs() -> None:
    rag_service.ingest_chunks(
        [
            Chunk(
                id="customer-support-handbook:p1-sla",
                document_id="customer-support-handbook",
                chunk_id="p1-sla",
                domain="customer_support",
                tenant_id="demo",
                doc_type="kb",
                access_roles=list(DEMO_ROLES),
                section_path="p1-sla",
                filename="customer_support_handbook.md",
                page=1,
                text=(
                    "Enterprise customer P1 support incidents require first response within 15 minutes. "
                    "SLA escalation must notify the duty manager."
                ),
                metadata={"tenant_id": "demo", "access_roles": list(DEMO_ROLES)},
            )
        ],
        replace=True,
    )


def test_settings_exposes_auth_config() -> None:
    assert isinstance(settings.auth_enabled, bool)
    assert isinstance(settings.demo_api_key, str)


def test_rag_debug_rejects_missing_token_when_auth_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTH_ENABLED", "true")
    monkeypatch.setenv("DEMO_API_KEY", "test-key")

    response = client.post("/rag/debug", json={"query": "P1 SLA"})

    assert response.status_code == 401


def test_rag_debug_rejects_wrong_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTH_ENABLED", "true")
    monkeypatch.setenv("DEMO_API_KEY", "test-key")

    response = client.post("/rag/debug", headers={"x-api-key": "wrong"}, json={"query": "P1 SLA"})

    assert response.status_code == 403


def test_rag_debug_accepts_demo_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTH_ENABLED", "true")
    monkeypatch.setenv("DEMO_API_KEY", "test-key")

    response = client.post(
        "/rag/debug",
        headers={"x-api-key": "test-key", "x-user-id": "u1", "x-tenant-id": "tenant-a", "x-roles": "reader"},
        json={"query": "P1 SLA"},
    )

    assert response.status_code == 200
    assert "results" in response.json()


def test_rag_query_rejects_missing_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTH_ENABLED", "true")
    monkeypatch.setenv("DEMO_API_KEY", "test-key")

    response = client.post(
        "/rag/query",
        json={"question": "enterprise customer P1 response time", "domain": "auto", "top_k": 5},
    )

    assert response.status_code in {401, 403}


def test_rag_query_rejects_wrong_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTH_ENABLED", "true")
    monkeypatch.setenv("DEMO_API_KEY", "test-key")

    response = client.post(
        "/rag/query",
        headers={"X-API-Key": "wrong-key"},
        json={"question": "enterprise customer P1 response time", "domain": "auto", "top_k": 5},
    )

    assert response.status_code in {401, 403}


def test_valid_api_key_generates_demo_auth_context(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTH_ENABLED", "true")
    monkeypatch.setenv("DEMO_API_KEY", "test-key")

    auth = require_auth(api_key="test-key")

    assert auth.user_id == "demo-user"
    assert auth.tenant_id == "demo"
    assert auth.roles == DEMO_ROLES


def test_demo_auth_context_can_access_demo_sample_docs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTH_ENABLED", "true")
    monkeypatch.setenv("DEMO_API_KEY", "test-key")
    _seed_demo_support_docs()
    auth = require_auth(api_key="test-key")

    debug = rag_service.debug_query(
        "enterprise customer P1 response time",
        top_k=5,
        context=auth.to_rag_context(),
    )

    assert debug["selected_domain"] == "customer_support"
    assert debug["sources"]
    assert debug["sources"][0]["tenant_id"] == "demo"
    assert "employee" in debug["sources"][0]["access_roles"]


def test_rag_query_valid_key_returns_customer_support_p1_sources(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTH_ENABLED", "true")
    monkeypatch.setenv("DEMO_API_KEY", "test-key")
    _seed_demo_support_docs()

    response = client.post(
        "/rag/query",
        headers=AUTH_HEADERS,
        json={"question": "enterprise customer P1 response time", "domain": "auto", "top_k": 5},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["answer"]
    assert data["sources"]
    assert data["sources"][0]["domain"] == "customer_support"
    assert data["sources"][0]["chunk_id"] == "p1-sla"
