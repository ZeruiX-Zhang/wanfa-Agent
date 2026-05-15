from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_openapi_docs_use_chinese_labels():
    schema = TestClient(app).get("/openapi.json").json()

    assert schema["info"]["title"] == "\u4f01\u4e1a\u77e5\u8bc6\u5e93 RAG Agent Demo"
    assert [tag["name"] for tag in schema["tags"]] == [
        "\u5065\u5eb7\u68c0\u67e5",
        "\u6587\u6863\u5904\u7406",
        "RAG \u95ee\u7b54",
        "\u5de5\u4f5c\u6d41 Agent",
        "RAG \u8bc4\u6d4b",
    ]
    assert schema["paths"]["/documents/ingest-local"]["post"]["summary"] == "\u5bfc\u5165\u672c\u5730\u6587\u6863"
    assert schema["paths"]["/agent/run"]["post"]["summary"] == "\u8fd0\u884c Agent"
