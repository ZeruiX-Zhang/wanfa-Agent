from __future__ import annotations

from tests.conftest import client


def test_knowledge_os_sources_and_claims_are_readable() -> None:
    sources = client.get("/api/knowledge-os/sources")
    assert sources.status_code == 200
    assert sources.json()
    assert "filename" in sources.json()[0]
    assert "D:\\" not in str(sources.json()[0])

    claims = client.get("/api/knowledge-os/claims")
    assert claims.status_code == 200
    assert any(item["id"] == "claim_desktop_workspaces" for item in claims.json())


def test_level_up_writes_knowledge_os_and_approve_writes_graph() -> None:
    level_up = client.post(
        "/api/level-up",
        json={
            "selected_text": "PromptAgent 右键菜单仍然只保留 Prompt 和 Level Up。",
            "title": "Context menu boundary",
            "source": "test",
            "collection": "product",
            "tags": ["desktop", "context-menu"],
        },
    )
    assert level_up.status_code == 200
    result = level_up.json()["level_up_result"]
    assert result["source_page"].startswith("wiki/sources/")
    assert result["claims"]
    assert result["nodes"]
    assert result["review_item_id"]

    queue = client.get("/api/level-up/review-queue")
    assert queue.status_code == 200
    assert any(item["id"] == result["review_item_id"] for item in queue.json())

    approve = client.post(f"/api/level-up/review/{result['review_item_id']}/approve")
    assert approve.status_code == 200
    assert approve.json()["status"] == "approved"

    nodes = client.get("/api/knowledge-os/graph/nodes")
    assert nodes.status_code == 200
    assert any(item["id"] == result["nodes"][0]["id"] for item in nodes.json())


def test_graph_review_detail_and_edit() -> None:
    queue = client.get("/api/level-up/review-queue").json()
    review_id = queue[0]["id"]
    detail = client.get(f"/api/level-up/review/{review_id}")
    assert detail.status_code == 200
    assert "claims" in detail.json()
    update = client.put(f"/api/level-up/review/{review_id}", json={"summary": "updated summary"})
    assert update.status_code == 200
    assert update.json()["summary"] == "updated summary"


def test_personal_api_reads_knowledge_os_personal_path() -> None:
    files = client.get("/api/knowledge-os/personal/files")
    assert files.status_code == 200
    ids = {item["id"] for item in files.json()}
    assert {"profile", "preferences", "goals", "current_projects", "writing_style", "learning_style", "decision_history"} <= ids

    profile = client.get("/api/knowledge-os/personal/files/profile")
    assert profile.status_code == 200
    assert profile.json()["filename"] == "profile.md"


def test_logs_api_returns_entries() -> None:
    logs = client.get("/api/knowledge-os/logs")
    assert logs.status_code == 200
    assert "entries" in logs.json()

