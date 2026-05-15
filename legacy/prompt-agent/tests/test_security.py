from __future__ import annotations

from tests.conftest import client


def test_path_traversal_is_rejected() -> None:
    bad_source = client.get("/api/knowledge-os/sources/..%2Fevil")
    assert bad_source.status_code in {400, 404}
    bad_personal = client.get("/api/knowledge-os/personal/files/..%2Fprofile")
    assert bad_personal.status_code in {400, 404}
    assert "knowledge_os" not in str(bad_source.json()).lower()


def test_api_key_is_not_returned() -> None:
    update = client.post(
        "/api/settings/model",
        json={
            "vendor": "custom",
            "provider": "openai_compatible",
            "base_url": "https://example.invalid/v1",
            "model": "custom-model",
            "api_key": "sk-secret-not-returned",
            "api_key_env": "OPENAI_API_KEY",
            "local_only": True,
            "allow_cloud_model": False,
            "redact_sensitive_info": True,
            "personal_wiki_enabled": True,
            "allow_cloud_personal_summary": False,
            "allow_cloud_sensitive_personal": False,
        },
    )
    assert update.status_code == 200
    body = update.json()
    assert body["has_api_key"] is True
    assert "api_key" not in body
    assert "sk-secret-not-returned" not in str(body)

    readback = client.get("/api/settings/model")
    assert readback.status_code == 200
    assert "sk-secret-not-returned" not in str(readback.json())

    client.post(
        "/api/settings/model",
        json={
            "vendor": "mock",
            "provider": "mock",
            "base_url": "",
            "model": "mock-prompt-model",
            "api_key_env": "OPENAI_API_KEY",
            "local_only": True,
            "allow_cloud_model": False,
            "redact_sensitive_info": True,
            "personal_wiki_enabled": True,
            "allow_cloud_personal_summary": False,
            "allow_cloud_sensitive_personal": False,
        },
    )
