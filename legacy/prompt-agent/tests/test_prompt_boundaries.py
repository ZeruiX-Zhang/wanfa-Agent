from __future__ import annotations

from tests.conftest import client


def test_prompt_default_does_not_read_knowledge_os() -> None:
    response = client.post(
        "/api/generate",
        json={
            "selected_text": "把桌面端改成三个工作区。",
            "user_goal": "生成实现计划",
            "mode": "prompt_from_idea",
            "user_id": "default",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["knowledge_os_info"]["used"] is False
    assert body["knowledge_os_info"]["sources"] == []
    assert body["knowledge_os_info"]["claims"] == []
    assert body["knowledge_os_info"]["graph"] == []
    assert body["context_budget"]["used_knowledge_tokens"] == 0
    assert body["context_budget"]["used_graph_tokens"] == 0


def test_prompt_can_read_knowledge_os_only_when_enabled() -> None:
    response = client.post(
        "/api/generate",
        json={
            "selected_text": "PromptAgent desktop workspaces",
            "user_goal": "生成产品说明提示词",
            "mode": "prompt_from_idea",
            "user_id": "default",
            "use_knowledge_os": True,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["knowledge_os_info"]["used"] is True
    assert body["context_budget"]["used_knowledge_tokens"] > 0 or body["context_budget"]["used_graph_tokens"] > 0


def test_personalization_off_prevents_personal_reads() -> None:
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
            "personal_wiki_enabled": False,
            "allow_cloud_personal_summary": False,
            "allow_cloud_sensitive_personal": False,
        },
    )
    response = client.post(
        "/api/generate",
        json={
            "selected_text": "不要读取个人资料。",
            "user_goal": "生成提示词",
            "mode": "prompt_from_idea",
            "user_id": "default",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["personalization_info"]["enabled"] is False
    assert body["personalization_info"]["used"] is False
    assert body["personalization_info"]["used_files"] == []

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

