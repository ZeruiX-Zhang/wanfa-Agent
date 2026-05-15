from __future__ import annotations


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_source_crud(client):
    payload = {
        "name": "Test RSS",
        "type": "rss",
        "category": "ai_news",
        "url": "https://example.com/rss.xml",
        "trust_score": 0.7,
        "language": "en",
        "country": "US",
    }
    created = client.post("/api/sources", json=payload)
    assert created.status_code == 201
    source_id = created.json()["id"]

    listed = client.get("/api/sources?category=ai_news")
    assert listed.status_code == 200
    assert listed.json()["total"] == 1

    patched = client.patch(f"/api/sources/{source_id}", json={"enabled": False, "trust_score": 0.4})
    assert patched.status_code == 200
    assert patched.json()["enabled"] is False
    assert patched.json()["trust_score"] == 0.4

    deleted = client.delete(f"/api/sources/{source_id}")
    assert deleted.status_code == 204


def test_source_policy_and_compliance_api(client):
    created = client.post(
        "/api/sources",
        json={
            "name": "Policy RSS",
            "type": "rss",
            "category": "ai_news",
            "url": "https://example.com/rss.xml",
        },
    )
    assert created.status_code == 201
    source_id = created.json()["id"]

    policy = client.get(f"/api/sources/{source_id}/policy")
    assert policy.status_code == 200
    assert policy.json()["source_id"] == source_id

    patched = client.patch(
        f"/api/sources/{source_id}/policy",
        json={"robots_txt_status": "allow", "compliance_status": "approved", "allowed_uses": ["metadata", "snippet", "link"]},
    )
    assert patched.status_code == 200
    assert patched.json()["compliance_status"] == "approved"

    decision = client.post(f"/api/sources/{source_id}/compliance/evaluate", json={"mode": "verified"})
    assert decision.status_code == 200
    assert decision.json()["decision"] in {"allow", "allow_limited"}


def test_manual_intelligence_object_api(client):
    created = client.post(
        "/api/intelligence-objects",
        json={
            "object_type": "market_signal",
            "title": "Demo signal",
            "summary": "A manually entered signal.",
            "domain": "ai",
            "language": "en",
            "mode": "speed",
            "scores": {
                "credibility": 0.4,
                "novelty": 0.5,
                "impact": 0.6,
                "actionability": 0.3,
                "urgency": 0.4,
            },
        },
    )
    assert created.status_code == 201
    object_id = created.json()["id"]

    listed = client.get("/api/intelligence-objects?domain=ai")
    assert listed.status_code == 200
    assert listed.json()["total"] == 1

    detail = client.get(f"/api/intelligence-objects/{object_id}")
    assert detail.status_code == 200
    assert detail.json()["aggregate_score"] > 0


def test_jobs_and_reports_mode_api(client):
    created = client.post(
        "/api/jobs",
        json={"name": "Speed smoke run", "type": "daily", "mode": "speed", "run_now": False, "parameters": {"limit": 1}},
    )
    assert created.status_code == 201
    job_id = created.json()["id"]
    assert created.json()["mode"] == "speed"

    run = client.post(f"/api/jobs/{job_id}/run")
    assert run.status_code == 200
    assert run.json()["status"] == "completed"

    reports = client.get("/api/reports?mode=speed")
    assert reports.status_code == 200
    assert reports.json()["total"] == 1
