from __future__ import annotations


def _headers() -> dict[str, str]:
    return {"X-API-Key": "change-me"}


def test_production_health_and_tools(client):
    health = client.get("/api/health")
    assert health.status_code == 200
    assert "components" in health.json()
    tools = client.get("/api/tools", headers=_headers())
    assert tools.status_code == 200
    names = {tool["name"] for tool in tools.json()["tools"]}
    assert "search_knowledge_base" in names
    assert "create_ticket_mock" in names


def test_production_rag_data_and_trace(client):
    rag = client.post(
        "/api/rag/query",
        headers=_headers(),
        json={"question": "What is the enterprise customer P1 response time?", "top_k": 5},
    )
    assert rag.status_code == 200
    payload = rag.json()
    assert payload["citations"]
    trace_id = payload["trace_id"]

    sql_check = client.post(
        "/api/data-agent/sql/check",
        headers=_headers(),
        json={"sql": "DROP TABLE orders"},
    )
    assert sql_check.status_code == 200
    assert sql_check.json()["is_valid"] is False

    trace = client.get(f"/api/traces/{trace_id}", headers=_headers())
    assert trace.status_code == 200
    assert trace.json()["trace_id"] == trace_id
