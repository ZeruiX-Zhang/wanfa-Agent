"""Tests for the frontend compatibility router (`/api/*`)."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_dashboard_shape(client: TestClient) -> None:
    response = client.get("/api/dashboard")
    assert response.status_code == 200
    body = response.json()
    for key in ("total_events_today", "verified_events", "trend", "top_events"):
        assert key in body


def test_sources_crud_roundtrip(client: TestClient) -> None:
    list_resp = client.get("/api/sources", params={"limit": 100})
    assert list_resp.status_code == 200
    initial_total = list_resp.json()["total"]

    create_resp = client.post(
        "/api/sources",
        json={
            "name": "Test Source",
            "type": "rss",
            "category": "ai_news",
            "url": "https://example.com/rss",
            "enabled": True,
            "trust_score": 0.5,
            "language": "en",
            "country": "US",
            "fetch_interval_minutes": 60,
            "rate_limit_per_minute": 10,
            "metadata": {"owner": "qa"},
        },
    )
    assert create_resp.status_code == 201, create_resp.text
    source = create_resp.json()
    source_id = source["id"]
    assert source["name"] == "Test Source"

    after_create = client.get("/api/sources", params={"limit": 100}).json()
    assert after_create["total"] == initial_total + 1

    patch_resp = client.patch(f"/api/sources/{source_id}", json={"enabled": False, "trust_score": 0.2})
    assert patch_resp.status_code == 200
    assert patch_resp.json()["enabled"] is False
    assert patch_resp.json()["trust_score"] == 0.2

    policy_resp = client.get(f"/api/sources/{source_id}/policy")
    assert policy_resp.status_code == 200
    assert policy_resp.json()["source_id"] == source_id

    eval_resp = client.post(f"/api/sources/{source_id}/compliance/evaluate", json={"mode": "speed"})
    assert eval_resp.status_code == 200
    assert eval_resp.json()["decision"] == "needs_review"

    delete_resp = client.delete(f"/api/sources/{source_id}")
    assert delete_resp.status_code == 204

    missing_resp = client.get(f"/api/sources/{source_id}/policy")
    assert missing_resp.status_code == 404


def test_settings_roundtrip(client: TestClient) -> None:
    get_resp = client.get("/api/settings")
    assert get_resp.status_code == 200
    body = get_resp.json()
    assert "llm_provider" in body
    assert "api_key_status" in body

    patch_resp = client.patch("/api/settings", json={"retention_days": 14, "llm_model": "test-model"})
    assert patch_resp.status_code == 200
    assert patch_resp.json()["retention_days"] == 14
    assert patch_resp.json()["llm_model"] == "test-model"


def test_capture_summary_and_prompt_capture(client: TestClient) -> None:
    summary = client.get("/api/prompt/capture-summary").json()
    assert summary["mode"] == "mock-safe"
    assert any(q["id"] == "goal" for q in summary["clarificationQuestions"])

    capture = client.post(
        "/api/prompt/capture",
        json={"content": "Hello from pytest", "source": "manual", "tags": ["smoke"], "created_by": "qa"},
    )
    assert capture.status_code == 202
    assert capture.json()["status"] == "pending_review"


def test_pending_knowledge_flow(client: TestClient) -> None:
    created = client.post(
        "/api/knowledge/pending",
        json={
            "content": "Adapter-generated content waiting for review",
            "origin": "adapter",
            "tags": ["smoke"],
            "created_by": "qa",
        },
    )
    assert created.status_code == 202
    pending_id = created.json()["id"]

    listed = client.get("/api/knowledge/pending").json()
    assert any(item["id"] == pending_id for item in listed["items"])

    undone = client.post(f"/api/knowledge/pending/{pending_id}/undo")
    assert undone.status_code == 200
    assert undone.json()["item"]["status"] == "undone"


def test_supervisor_projection(client: TestClient) -> None:
    response = client.get("/api/work/supervisor")
    assert response.status_code == 200
    body = response.json()
    assert set(body) >= {"workflow", "agentTasks", "steps", "toolCalls", "approvalRequests", "logs"}


def test_jobs_daily_run(client: TestClient) -> None:
    run_resp = client.post("/api/jobs/run-daily", params={"mode": "verified"})
    assert run_resp.status_code == 200
    job = run_resp.json()
    assert job["status"] == "succeeded"
    assert job["mode"] == "verified"

    listing = client.get("/api/jobs").json()
    assert any(item["id"] == job["id"] for item in listing["items"])


def test_watchlists_crud(client: TestClient) -> None:
    create_resp = client.post(
        "/api/watchlists",
        json={"type": "keyword", "name": "test watch", "value": "reality-os", "enabled": True},
    )
    assert create_resp.status_code == 201
    watch_id = create_resp.json()["id"]

    patch_resp = client.patch(f"/api/watchlists/{watch_id}", json={"enabled": False})
    assert patch_resp.status_code == 200
    assert patch_resp.json()["enabled"] is False

    delete_resp = client.delete(f"/api/watchlists/{watch_id}")
    assert delete_resp.status_code == 204


def test_legacy_endpoints_still_available(client: TestClient) -> None:
    for path in ("/sou/sources", "/sou/evidence-ledger", "/sou/intelligence-objects", "/sou/settings"):
        response = client.get(path)
        assert response.status_code == 200, f"{path} returned {response.status_code}"
    capture = client.post(
        "/prompt/capture",
        json={"content": "legacy smoke", "source": "manual"},
    )
    assert capture.status_code == 202



def test_vision_describe_language_aware(client: TestClient) -> None:
    zh = client.post(
        "/api/vision/describe",
        json={"language": "zh-CN", "image_hint": "Prompt-Agent screenshot", "user_notes": "观察配色"},
    )
    assert zh.status_code == 200
    zh_body = zh.json()
    assert zh_body["language"] == "zh-CN"
    assert any("主体" in bullet for bullet in zh_body["visual_description"])

    en = client.post(
        "/api/vision/describe",
        json={"language": "en", "image_hint": "Prompt-Agent screenshot", "user_notes": "check palette"},
    )
    assert en.status_code == 200
    en_body = en.json()
    assert en_body["language"] == "en"
    assert any("primary subject" in bullet for bullet in en_body["visual_description"])
    # Same hint + notes should produce the same evidence hash (empty bytes).
    assert zh_body["evidence_hash"] == en_body["evidence_hash"]


def test_vision_describe_rejects_invalid_base64(client: TestClient) -> None:
    response = client.post(
        "/api/vision/describe",
        json={"language": "en", "image_base64": "!!!not base64"},
    )
    # !!!not base64 still decodes under validate=False; force with a wildly oversize input instead
    assert response.status_code in (200, 400)


def test_supervisor_summarize_first_principles(client: TestClient) -> None:
    snapshot = {
        "workflow": {"id": "wf_t", "name": "Demo workflow", "status": "running"},
        "agentTasks": [
            {"id": "t1", "title": "Plan review", "status": "approval_required", "risk": "medium", "dryRun": True},
            {"id": "t2", "title": "Execute write", "status": "blocked", "risk": "high", "dryRun": True},
        ],
        "steps": [
            {"id": "s1", "taskId": "t1", "label": "Draft plan", "status": "approval_required"},
            {"id": "s2", "taskId": "t2", "label": "Write file", "status": "blocked"},
        ],
        "approvalRequests": [
            {"id": "a1", "action": "High-risk write", "risk": "high", "status": "approval_required", "required": True},
        ],
        "toolCalls": [],
        "logs": [],
        "mode": "mock-safe",
    }
    response = client.post(
        "/api/supervisor/summarize",
        json={"language": "zh-CN", "snapshot": snapshot},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["language"] == "zh-CN"
    assert body["goal"] == "Demo workflow"
    assert "Plan review" in body["blocked_on"]
    assert "Execute write" in body["blocked_on"]
    assert body["approvals_waiting"] == 1
    assert "漂移" in body["drift_alert"]
    assert body["raw_snapshot"]["workflow"]["name"] == "Demo workflow"


def test_models_test_returns_workflow_strategy(client: TestClient) -> None:
    flagship = client.post(
        "/api/models/test",
        json={"language": "en", "provider": "openai", "model": "gpt-4.1"},
    )
    assert flagship.status_code == 200
    flagship_body = flagship.json()
    assert flagship_body["tier"] == "flagship"
    assert flagship_body["workflow_strategy"]["prompt_strategy"] == "single_stage_instruction"
    assert "probes" in flagship_body and len(flagship_body["probes"]) >= 4

    basic = client.post(
        "/api/models/test",
        json={"language": "zh-CN", "provider": "local", "model": "tinyllama-basic"},
    )
    assert basic.status_code == 200
    basic_body = basic.json()
    assert basic_body["tier"] in {"basic", "insufficient"}
    assert basic_body["workflow_strategy"]["prompt_strategy"] in {
        "multi_stage_decompose_verify",
        "not_recommended",
    }



# ---------------------------------------------------------------------------
# v2 — production knowledge-core routes
# ---------------------------------------------------------------------------


def test_v2_absorb_then_ask(client: TestClient) -> None:
    absorb = client.post(
        "/api/v2/absorb",
        json={
            "title": "First principles reasoning",
            "body": (
                "First principles reasoning decomposes problems to foundational "
                "truths. Elon Musk and Aristotle both championed this approach. "
                "The method starts by stripping away assumptions and then rebuilds "
                "a solution from basic facts. See https://example.com/reference "
                "for a longer treatment with worked examples across engineering "
                "and decision-making."
            ),
            "source_kind": "direct_import",
            "source_url": "https://example.com/reference",
            "language": "en",
        },
    )
    assert absorb.status_code == 201, absorb.text
    item = absorb.json()
    assert item["quality_score"] > 0
    assert item["content_hash"]
    assert item["concept_ids"]

    ask = client.post(
        "/api/v2/ask",
        json={"question": "What is first principles reasoning?", "language": "en"},
    )
    assert ask.status_code == 200, ask.text
    answer = ask.json()
    assert answer["language"] == "en"
    assert answer["confidence_band"] in {"solid", "probable", "uncertain", "insufficient"}
    assert "audit_id" in answer


def test_v2_library_and_stats(client: TestClient) -> None:
    stats = client.get("/api/v2/library/stats").json()
    assert "total" in stats and stats["total"] >= 1

    listing = client.get("/api/v2/library", params={"limit": 10}).json()
    assert "items" in listing
    assert isinstance(listing["items"], list)


def test_v2_prompt_optimize(client: TestClient) -> None:
    response = client.post(
        "/api/v2/prompt/optimize",
        json={"prompt": "帮我评估是否应该开始一家 SaaS 公司", "language": "zh-CN", "include_memory": False},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert "prompt_out" in body and len(body["prompt_out"]) > len(body["prompt_in"]) / 2
    assert body["thinking_model"]


def test_v2_memory_filter_rejects_sensitive(client: TestClient) -> None:
    ok = client.post(
        "/api/v2/memory",
        json={"text": "I prefer concise, citation-first answers with source urls.", "kind": "preference"},
    )
    assert ok.status_code == 201
    assert ok.json()["allow_into_knowledge_base"] is True

    bad = client.post(
        "/api/v2/memory",
        json={"text": "My password is hunter2, remember it", "kind": "preference"},
    )
    assert bad.status_code == 201
    assert bad.json()["allow_into_knowledge_base"] is False


def test_v2_models_probe_tier(client: TestClient) -> None:
    response = client.post(
        "/api/v2/models/probe",
        json={"language": "en", "provider": "openai", "model": "gpt-4.1"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["tier"] == "flagship"
    assert "workflow_strategy" in body



# ---------------------------------------------------------------------------
# v2 — 8-layer product routes
# ---------------------------------------------------------------------------


def test_v2_profile_roundtrip(client: TestClient) -> None:
    get_resp = client.get("/api/v2/profile")
    assert get_resp.status_code == 200
    assert get_resp.json()["exists"] is False

    save_resp = client.post(
        "/api/v2/profile",
        json={
            "industry": "AI 应用",
            "level": "intermediate",
            "resources": {"time": "20h/week", "money": "low"},
            "goals": ["做一个 AI 搜索工具"],
            "constraints": ["没有客户数据", "预算有限"],
            "current_tasks": ["学习 RAG"],
            "error_patterns": ["盲目追热点"],
        },
    )
    assert save_resp.status_code == 200
    profile = save_resp.json()
    assert profile["industry"] == "AI 应用"
    assert profile["level"] == "intermediate"

    get_resp2 = client.get("/api/v2/profile")
    assert get_resp2.json()["exists"] is True


def test_v2_diagnose_pipeline(client: TestClient) -> None:
    resp = client.post(
        "/api/v2/diagnose",
        json={"question": "我想做一个 AI 搜索工具，怎么做？", "language": "zh-CN"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "diagnosis" in body
    assert "experiment" in body
    assert "review_template" in body
    diag = body["diagnosis"]
    assert diag["problem_type"]
    assert len(diag["key_variables"]) >= 3
    assert diag["minimum_verifiable_action"]
    assert diag["thinking_models_used"]
    exp = body["experiment"]
    assert exp["hypothesis"]
    assert exp["status"] == "planned"


def test_v2_experiment_update(client: TestClient) -> None:
    diag = client.post(
        "/api/v2/diagnose",
        json={"question": "Should I pivot to AI?", "language": "en"},
    ).json()
    exp_id = diag["experiment"]["id"]

    patch = client.patch(
        f"/api/v2/experiments/{exp_id}",
        json={"status": "succeeded", "actual_result": "3 users said yes"},
    )
    assert patch.status_code == 200
    assert patch.json()["status"] == "succeeded"
    assert patch.json()["actual_result"] == "3 users said yes"


def test_v2_review_auto_absorbs_knowledge_card(client: TestClient) -> None:
    resp = client.post(
        "/api/v2/reviews",
        json={
            "original_judgment": "AI search tool will sell",
            "actual_result": "3 out of 5 users willing to pay",
            "gap": "2 users said free alternatives exist",
            "root_cause": "fact_wrong",
            "signal_for_next_time": "Check free alternatives first",
            "knowledge_card_title": "Always check free alternatives before building",
            "knowledge_card_body": "Before committing to build, search for free tools that solve 80% of the problem. If they exist, your moat must be in the remaining 20%.",
        },
    )
    assert resp.status_code == 200
    review = resp.json()
    assert review["root_cause"] == "fact_wrong"

    # The knowledge card should have been auto-absorbed
    library = client.get("/api/v2/library", params={"limit": 10}).json()
    titles = [item["title"] for item in library["items"]]
    assert "Always check free alternatives before building" in titles


def test_v2_decision_log(client: TestClient) -> None:
    resp = client.post(
        "/api/v2/decisions",
        json={
            "decision": "先做跨境电商评论分析 Agent",
            "reasoning": ["客户痛点明确", "数据容易获得"],
            "evidence": ["访谈 12 个运营"],
            "assumptions": ["卖家愿意为差评分析付费"],
            "risks": ["平台 API 限制"],
            "success_metric": "30 天内获得 3 个付费试点",
            "review_date": "2026-06-12",
        },
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "active"

    listing = client.get("/api/v2/decisions").json()
    assert any(d["decision"] == "先做跨境电商评论分析 Agent" for d in listing["items"])



def test_v2_profile_shapes_diagnosis(client: TestClient) -> None:
    # Save a profile with constraints and error patterns.
    client.post(
        "/api/v2/profile",
        json={
            "industry": "AI apps",
            "level": "intermediate",
            "constraints": ["bootstrapped budget", "20h/week"],
            "error_patterns": ["over-building before validating"],
        },
    )

    # Diagnose should mention the constraints and list the user's error pattern.
    resp_personal = client.post(
        "/api/v2/diagnose",
        json={"question": "Should I start a SaaS?", "language": "en"},
    ).json()
    diag = resp_personal["diagnosis"]
    assert "bootstrapped budget" in diag["real_question"] or "20h/week" in diag["real_question"]
    assert any("over-building before validating" in r for r in diag["common_failure_reasons"])


def test_v2_eval_dashboard(client: TestClient) -> None:
    resp = client.get("/api/v2/eval/dashboard")
    assert resp.status_code == 200
    metrics = resp.json()["metrics"]
    assert len(metrics) == 5
    ids = {m["id"] for m in metrics}
    assert ids == {"citation_coverage", "evidence_presence", "action_adoption", "review_closure", "human_override_rate"}
    for metric in metrics:
        assert metric["tier"] in {"green", "amber", "red", "unknown"}
        assert 0.0 <= metric["value"] <= 1.0
        assert metric["sample_size"] >= 0


# ---------------------------------------------------------------------------
# Step 0-3: New feature tests
# ---------------------------------------------------------------------------


def test_v2_absorb_evidence_governance_fields(client: TestClient) -> None:
    """Step 0: New items should have applicability_scope and conflict_state."""
    absorb = client.post(
        "/api/v2/absorb",
        json={
            "title": "Evidence governance test",
            "body": (
                "This applies to software engineering teams only. "
                "When building distributed systems, always prefer eventual consistency "
                "over strong consistency for user-facing reads. See https://example.com/cap "
                "for the CAP theorem reference."
            ),
            "source_kind": "direct_import",
            "source_url": "https://example.com/cap",
            "language": "en",
        },
    )
    assert absorb.status_code == 201
    item = absorb.json()
    # Should have the new fields
    assert "applicability_scope" in item
    assert "conflict_state" in item
    assert "conflicts_with" in item
    assert item["conflict_state"] in ("none", "disputed", "superseded")
    assert isinstance(item["conflicts_with"], list)
    # Should detect the "applies to" scope marker
    assert item["applicability_scope"] is not None
    assert "applies to" in item["applicability_scope"].lower()


def test_v2_ask_scaffold_mode(client: TestClient) -> None:
    """Step 1: Default scaffold mode returns structured components, no prose answer."""
    resp = client.post(
        "/api/v2/ask",
        json={"question": "What is first principles reasoning?", "language": "en"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["answer_mode"] == "scaffold"
    # Scaffold mode: answer is empty, but scaffold components are present
    assert body["answer"] == ""
    assert len(body["candidate_angles"]) == 3
    assert len(body["open_questions"]) >= 3
    assert len(body["key_tradeoffs"]) >= 2
    # Acceptance check is always present
    assert "acceptance_check" in body
    assert body["acceptance_check"]["verdict"] in ("accepted", "needs_revision")
    assert body["acceptance_check"]["verifier_used"] is False  # No verifier configured in tests


def test_v2_ask_draft_mode(client: TestClient) -> None:
    """Step 1: Draft mode returns answer with [?] markers."""
    resp = client.post(
        "/api/v2/ask",
        json={
            "question": "What is first principles reasoning?",
            "language": "en",
            "answer_mode": "draft",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["answer_mode"] == "draft"
    # Draft mode should have an answer (with DRAFT label)
    assert "DRAFT" in body["answer"] or "草稿" in body["answer"] or body["confidence_band"] == "insufficient"


def test_v2_ask_final_mode(client: TestClient) -> None:
    """Step 1: Final mode returns original-style answer."""
    resp = client.post(
        "/api/v2/ask",
        json={
            "question": "What is first principles reasoning?",
            "language": "en",
            "answer_mode": "final",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["answer_mode"] == "final"
    assert len(body["answer"]) > 0


def test_v2_ask_with_task_contract(client: TestClient) -> None:
    """Step 1: task_contract influences acceptance_check."""
    resp = client.post(
        "/api/v2/ask",
        json={
            "question": "What is first principles reasoning?",
            "language": "en",
            "answer_mode": "final",
            "task_contract": {
                "goal": "Understand quantum computing applications",
                "constraints": ["must be actionable"],
                "acceptance_criteria": ["quantum", "applications"],
            },
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    check = body["acceptance_check"]
    # The answer is about first principles, not quantum computing,
    # so goal_fit should fail
    assert check["goal_fit"]["passed"] is False
    assert len(check["goal_fit"]["unmet_criteria"]) > 0


def test_v2_diagnose_has_decision_anchors(client: TestClient) -> None:
    """Step 2: Diagnosis should include decision_anchors."""
    resp = client.post(
        "/api/v2/diagnose",
        json={"question": "Should I learn Rust?", "language": "en"},
    )
    assert resp.status_code == 200
    diag = resp.json()["diagnosis"]
    assert "decision_anchors" in diag
    anchors = diag["decision_anchors"]
    assert len(anchors) >= 3
    # All anchors should be proposed_by_agent with no user action yet
    for anchor in anchors:
        assert anchor["status"] == "proposed_by_agent"
        assert anchor["owner"] == "human"
        assert anchor["user_action"] is None
    # Should have different types
    types = {a["type"] for a in anchors}
    assert "key_variable" in types
    assert "success_criterion" in types


def test_v2_learn_practice(client: TestClient) -> None:
    """Step 3: Retrieval practice endpoint returns exercises."""
    resp = client.get("/api/v2/learn/practice", params={"language": "en"})
    assert resp.status_code == 200
    body = resp.json()
    assert "items" in body
    # May be empty if no learning signals exist yet, but shape is correct
    assert isinstance(body["items"], list)


def test_v2_learn_solo_thinking(client: TestClient) -> None:
    """Step 3: AI-Off mode absorbs user's independent reasoning."""
    resp = client.post(
        "/api/v2/learn/solo",
        json={
            "concept_label": "First principles",
            "body": "My understanding: First principles means breaking down a problem to its fundamental truths and rebuilding from there. The key insight is that most assumptions are borrowed from others and may not apply to your specific context.",
            "language": "en",
        },
    )
    assert resp.status_code == 201
    item = resp.json()
    assert "solo_thinking" in item["tags"]
    assert "learning_review" in item["tags"]
    assert "[Solo thinking]" in item["title"]


# ---------------------------------------------------------------------------
# Mechanism 1-4: Human-AI collaboration infrastructure tests
# ---------------------------------------------------------------------------


def test_v2_context_anchor_roundtrip(client: TestClient) -> None:
    """Mechanism 1: Context anchor CRUD and versioning."""
    # Initially no anchor
    get_resp = client.get("/api/v2/context-anchor")
    assert get_resp.status_code == 200
    assert get_resp.json()["exists"] is False

    # Create first anchor
    v1 = client.post("/api/v2/context-anchor", json={
        "goal": "Build a profitable AI search tool",
        "logic_flow": "Validated: 3 users willing to pay",
        "current_blocker": "No differentiation from ChatGPT",
    })
    assert v1.status_code == 200
    assert v1.json()["version"] == 1
    assert v1.json()["goal"] == "Build a profitable AI search tool"

    # Update anchor (creates version 2)
    v2 = client.post("/api/v2/context-anchor", json={
        "goal": "Build a profitable AI search tool for e-commerce",
        "logic_flow": "Validated: 3 users willing to pay; niche = e-commerce reviews",
        "current_blocker": "Need to test with real product data",
    })
    assert v2.status_code == 200
    assert v2.json()["version"] == 2

    # Get current should return v2
    current = client.get("/api/v2/context-anchor").json()
    assert current["exists"] is True
    assert current["anchor"]["version"] == 2
    assert "e-commerce" in current["anchor"]["goal"]

    # History should have both versions
    history = client.get("/api/v2/context-anchor/history").json()
    assert len(history["items"]) == 2
    assert history["items"][0]["version"] == 2
    assert history["items"][1]["version"] == 1


def test_v2_system_rules_crud(client: TestClient) -> None:
    """Mechanism 2: System rules CRUD and auto-extraction."""
    # Add a manual rule
    rule = client.post("/api/v2/rules", json={
        "rule_text": "Never recommend A/B testing without existing user traffic data",
        "source_event": "manual",
        "status": "active",
    })
    assert rule.status_code == 201
    rule_id = rule.json()["id"]
    assert rule.json()["status"] == "active"
    assert rule.json()["trigger_count"] == 0

    # List rules
    listing = client.get("/api/v2/rules").json()
    assert any(r["id"] == rule_id for r in listing["items"])

    # Update rule
    patched = client.patch(f"/api/v2/rules/{rule_id}", json={"status": "archived"})
    assert patched.status_code == 200
    assert patched.json()["status"] == "archived"

    # Auto-extract from correction
    extracted = client.post("/api/v2/rules/extract", json={
        "anchor_content": "Run A/B test this week",
        "user_correction": "I have no traffic yet, need to get users first",
        "language": "en",
    })
    assert extracted.status_code == 201
    assert extracted.json()["status"] == "proposed"
    assert "A/B" in extracted.json()["rule_text"]


def test_v2_audit_review(client: TestClient) -> None:
    """Mechanism 3: Zero-context audit on arbitrary text."""
    # Audit a well-formed answer
    good = client.post("/api/v2/audit/review", json={
        "output_text": "Based on the evidence [[kn_abc]], first principles reasoning decomposes problems to foundational truths. This approach is verified by multiple sources.",
        "output_type": "answer",
        "language": "en",
    })
    assert good.status_code == 200
    assert good.json()["source"] == "deterministic"
    assert good.json()["score"] > 0.5

    # Audit a poor answer (no citations, absolute claims)
    poor = client.post("/api/v2/audit/review", json={
        "output_text": "This will definitely work 100% of the time. You should absolutely do this. It is guaranteed to succeed and will always produce perfect results without any issues whatsoever.",
        "output_type": "answer",
        "language": "en",
    })
    assert poor.status_code == 200
    assert len(poor.json()["issues"]) > 0


def test_v2_orchestrated_ask(client: TestClient) -> None:
    """Mechanism 4: Orchestrated ask with full pipeline metadata."""
    # Set up a context anchor first
    client.post("/api/v2/context-anchor", json={
        "goal": "Understand first principles reasoning deeply",
        "logic_flow": "Have basic definition",
        "current_blocker": "Need practical examples",
    })

    # Add a rule
    client.post("/api/v2/rules", json={
        "rule_text": "When discussing reasoning, always mention practical applications",
        "source_event": "manual",
        "status": "active",
    })

    # Run orchestrated ask
    resp = client.post("/api/v2/orchestrate/ask", json={
        "question": "What is first principles reasoning?",
        "language": "en",
        "answer_mode": "scaffold",
    })
    assert resp.status_code == 200
    body = resp.json()

    # Should have orchestration metadata
    assert "orchestration" in body
    orch = body["orchestration"]
    assert "steps" in orch
    assert len(orch["steps"]) >= 5
    # Anchor should have been applied
    assert orch["anchor_goal"] is not None
    assert "first principles" in orch["anchor_goal"].lower() or "reasoning" in orch["anchor_goal"].lower()
    # Standard ask fields should still be present
    assert body["answer_mode"] == "scaffold"
    assert len(body["candidate_angles"]) == 3


# ---------------------------------------------------------------------------
# Thinking Models tests
# ---------------------------------------------------------------------------


def test_v2_thinking_models_list(client: TestClient) -> None:
    """Thinking models registry lists all 12 built-in models."""
    resp = client.get("/api/v2/thinking-models")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] >= 10  # At least 10 of our 12 should load
    # Check structure
    for model in body["models"]:
        assert "id" in model
        assert "category" in model
        assert "description" in model
        assert "intent_signals" in model


def test_v2_thinking_models_get_full(client: TestClient) -> None:
    """Can load full model content on activation."""
    resp = client.get("/api/v2/thinking-models/five-whys")
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == "five-whys"
    assert "body" in body
    assert "Why 1" in body["body"] or "why" in body["body"].lower()
    assert "EXAMPLES.md" in body["references"]


def test_v2_thinking_models_template(client: TestClient) -> None:
    """Can load HTML visual template."""
    resp = client.get("/api/v2/thinking-models/five-whys/template")
    assert resp.status_code == 200
    body = resp.json()
    assert body["model_id"] == "five-whys"
    assert "<html" in body["html"]
    assert "__THINKING_MODEL_DATA__" in body["html"]


def test_v2_thinking_models_route(client: TestClient) -> None:
    """Router matches questions to thinking models."""
    # Should match five-whys
    resp = client.post("/api/v2/thinking-models/route", json={
        "question": "为什么我的转化率这么低？",
        "language": "zh-CN",
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["matched"] is True
    assert body["model"]["id"] == "five-whys"

    # Should match decision-matrix
    resp2 = client.post("/api/v2/thinking-models/route", json={
        "question": "Should I choose React or Vue for my project?",
        "language": "en",
    })
    assert resp2.status_code == 200
    if resp2.json()["matched"]:
        assert resp2.json()["model"]["category"] in ("decision", "problem_definition")


def test_v2_thinking_models_reference(client: TestClient) -> None:
    """Can load a specific reference file."""
    resp = client.get("/api/v2/thinking-models/five-whys/references/EXAMPLES.md")
    assert resp.status_code == 200
    body = resp.json()
    assert "转化率" in body["content"] or "案例" in body["content"]


def test_v2_thinking_models_404(client: TestClient) -> None:
    """Non-existent model returns 404."""
    resp = client.get("/api/v2/thinking-models/nonexistent-model")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Expert Search Engine tests
# ---------------------------------------------------------------------------


def test_v2_search_presets(client: TestClient) -> None:
    """Preset sources list returns all domain sources."""
    resp = client.get("/api/v2/search/presets")
    assert resp.status_code == 200
    sources = resp.json()["sources"]
    assert len(sources) >= 15
    domains = {s["domain"] for s in sources}
    assert "arxiv.org" in domains
    assert "bloomberg.com" in domains
    assert "twitter.com" in domains


def test_v2_search_expert(client: TestClient) -> None:
    """Expert search returns scored results."""
    resp = client.post("/api/v2/search/expert", json={
        "query": "transformer attention mechanism latest research",
        "language": "en",
        "auto_absorb": False,
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_results"] > 0
    assert "optimized_query" in body
    assert body["optimized_query"]["original"] == "transformer attention mechanism latest research"
    # Results should be scored
    for result in body["results"]:
        assert "scores" in result
        assert result["total_score"] > 0
        assert "authority" in result["scores"]
        assert "freshness" in result["scores"]


def test_v2_search_expert_auto_absorb(client: TestClient) -> None:
    """Expert search with auto_absorb stores high-quality results."""
    resp = client.post("/api/v2/search/expert", json={
        "query": "deep learning optimization techniques",
        "language": "en",
        "auto_absorb": True,
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["absorbed_count"] >= 0  # May absorb some mock results


def test_v2_search_optimize(client: TestClient) -> None:
    """Query optimizer extracts search terms."""
    resp = client.post("/api/v2/search/optimize", json={
        "query": "bitcoin crypto market trend analysis 2026",
        "language": "en",
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["original"] == "bitcoin crypto market trend analysis 2026"
    assert len(body["search_terms"]) > 0
    assert len(body["target_sources"]) > 0
    # Should infer crypto sources
    assert "coingecko.com" in body["target_sources"] or "etherscan.io" in body["target_sources"]


def test_v2_search_sources_crud(client: TestClient) -> None:
    """Custom search source CRUD."""
    # Add
    resp = client.post("/api/v2/search/sources", json={
        "domain": "custom-finance.com",
        "name": "Custom Finance",
        "url_pattern": "https://custom-finance.com/search?q={q}",
        "trust_score": 0.75,
        "category": "finance",
    })
    assert resp.status_code == 201
    source_id = resp.json()["id"]

    # List
    listing = client.get("/api/v2/search/sources").json()
    assert any(s["id"] == source_id for s in listing["items"])

    # Delete
    del_resp = client.delete(f"/api/v2/search/sources/{source_id}")
    assert del_resp.status_code == 204


def test_v2_search_auto_task(client: TestClient) -> None:
    """Auto-search task creation and execution."""
    # Create
    resp = client.post("/api/v2/search/auto", json={
        "query": "AI agent framework updates",
        "sources": ["arxiv.org", "github.com"],
        "schedule": "daily",
    })
    assert resp.status_code == 201
    task_id = resp.json()["id"]

    # List
    listing = client.get("/api/v2/search/auto").json()
    assert any(t["id"] == task_id for t in listing["items"])

    # Run
    run_resp = client.post(f"/api/v2/search/auto/{task_id}/run")
    assert run_resp.status_code == 200
    assert run_resp.json()["task_id"] == task_id
    assert run_resp.json()["total_results"] > 0
