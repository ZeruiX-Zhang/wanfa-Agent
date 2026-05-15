from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_json_responses_advertise_utf8_charset():
    response = TestClient(app).get("/health")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json; charset=utf-8")
