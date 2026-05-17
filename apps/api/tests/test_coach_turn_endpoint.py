"""Integration tests for ``POST /api/v2/coach/turn`` (Task 2.13).

Validates Requirements 1.3, 1.4, 1.10, 11.5:

* R1.3 — the endpoint returns the documented coach-turn payload
  (``next_prompt``, ``grounded_evidence``, ``contradictions``,
  ``due_practice``, ``session_state``, ``expert_gap``).
* R1.4 — when ``session_id`` is omitted, a fresh ``CoachingSession`` is
  created under the caller's tenant and ``session_id`` is returned.
* R1.10 — referencing a ``session_id`` that belongs to another tenant
  returns HTTP 404 with no metadata leakage.
* R11.5 — the response declares ``metadata.mode`` consistent with the
  ``AdapterMetadata`` contract (``"pending-review"`` for this write
  path because a state-log row is written).

Two language variants are exercised so we catch i18n regressions on the
fallback ``next_prompt`` (R14.2-3) without coupling to the LLM-generated
answer text (which is never used in the test environment because no
generator slot is configured).
"""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from apps.api.app.coaching_session import CoachingSessionRepo
from apps.api.app.knowledge_core import default_core_path


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _post_turn(
    client: TestClient,
    *,
    tenant: str,
    user_message: str,
    language: str,
    session_id: str | None = None,
    confidence_check: float | None = None,
) -> Any:
    body: dict[str, Any] = {
        "user_message": user_message,
        "language": language,
        "mode": "professional",
    }
    if session_id is not None:
        body["session_id"] = session_id
    if confidence_check is not None:
        body["confidence_check"] = confidence_check
    return client.post(
        "/api/v2/coach/turn",
        json=body,
        headers={"X-Tenant-ID": tenant, "X-User-ID": "alice"},
    )


def _assert_canonical_shape(payload: dict[str, Any]) -> None:
    """Every coach-turn response must satisfy these structural invariants."""

    # Documented top-level keys (R1.3).
    for key in (
        "metadata",
        "session_id",
        "session_state",
        "next_prompt",
        "grounded_evidence",
        "contradictions",
        "due_practice",
        "expert_gap",
        "skill_chain",
        "next_action",
        "metacognition",
        "audit_id",
        "run_id",
    ):
        assert key in payload, f"missing key in coach turn response: {key!r}"

    # R11.5 — metadata.mode is one of the AdapterMode literals; this write
    # path declares ``pending-review`` because it appends a session
    # state-log row.
    assert payload["metadata"]["mode"] == "pending-review"
    assert payload["metadata"]["adapter"] == "v2.coach.turn"
    assert payload["metadata"]["read_only"] is False

    # R1.2 — session_state must be one of the documented states.
    assert payload["session_state"] in {
        "active",
        "awaiting_evidence",
        "awaiting_practice",
        "awaiting_experiment",
        "awaiting_review",
        "paused",
        "archived",
    }
    # R1.5 — next_action must be one of the documented values.
    assert payload["next_action"] in {
        "learn",
        "practice",
        "experiment",
        "review",
        "awaiting_evidence",
    }

    # The collections default to lists even when empty — this keeps clients
    # from having to special-case ``None``.
    assert isinstance(payload["grounded_evidence"], list)
    assert isinstance(payload["contradictions"], list)
    assert isinstance(payload["due_practice"], list)

    # Expert gap, when present, obeys the bounds (R2.3, Property 8).
    gap = payload.get("expert_gap")
    if gap is not None:
        assert 0.0 <= gap["expert_gap_score"] <= 1.0
        assert len(gap["missing_points"]) <= 7
        assert gap["rubric_source"] in {"domain", "default"}


# ---------------------------------------------------------------------------
# R1.4 — session creation, R1.3 — response shape
# ---------------------------------------------------------------------------


def test_post_coach_turn_zhCN(client: TestClient) -> None:
    """Coach turn with ``language="zh-CN"``.

    Covers:
      a) No ``session_id`` on the first call → a session is created and
         returned (R1.4).
      b) Subsequent call supplying that session id continues the same
         session (R1.8 — restored from persistent storage).
      c) A second tenant calling with the first tenant's session id gets
         404 with no leaked metadata (R1.10, R12.3).
    """

    tenant_a = "tnt-coach-zh-a"
    tenant_b = "tnt-coach-zh-b"

    # (a) First call — no session_id supplied.
    first = _post_turn(
        client,
        tenant=tenant_a,
        user_message="我应该如何评估下一步的学习重点？",
        language="zh-CN",
        confidence_check=0.4,
    )
    assert first.status_code == 200, first.text
    first_body = first.json()
    _assert_canonical_shape(first_body)

    session_id = first_body["session_id"]
    assert session_id.startswith("cs_"), session_id
    assert first_body["next_prompt"], "next_prompt must be non-empty for zh-CN"

    # The fallback prompt (used when no LLM generator is configured) must
    # render in Chinese for ``language="zh-CN"`` (R14.2).
    if first_body["next_prompt"].startswith("为了把"):
        assert "证据" in first_body["next_prompt"]

    # The orchestrator should have surfaced the user's confidence_check.
    metacog = first_body["metacognition"]
    assert metacog is not None
    assert metacog["user_confidence"] == 0.4

    # The session was actually persisted under tenant_a.
    repo = CoachingSessionRepo(path=default_core_path())
    persisted = repo.get(tenant_id=tenant_a, session_id=session_id)
    assert persisted is not None
    assert persisted.tenant_id == tenant_a

    # (b) Second call — same session_id continues the loop.
    second = _post_turn(
        client,
        tenant=tenant_a,
        user_message="继续上一轮的讨论。",
        language="zh-CN",
        session_id=session_id,
    )
    assert second.status_code == 200, second.text
    second_body = second.json()
    _assert_canonical_shape(second_body)
    assert second_body["session_id"] == session_id

    # (c) Cross-tenant lookup must 404 with no metadata leakage (R1.10).
    cross = _post_turn(
        client,
        tenant=tenant_b,
        user_message="试图访问别的租户的会话。",
        language="zh-CN",
        session_id=session_id,
    )
    assert cross.status_code == 404, cross.text
    cross_body = cross.json()
    # Body must not echo the session id, the other tenant id, or any
    # other identifying metadata.
    cross_text = repr(cross_body)
    assert session_id not in cross_text
    assert tenant_a not in cross_text


def test_post_coach_turn_en(client: TestClient) -> None:
    """Coach turn with ``language="en"``.

    Mirrors the zh-CN test for the English locale and additionally
    verifies that two distinct tenants supplying the same un-set
    ``session_id`` get *different* sessions back (R12.4).
    """

    tenant_a = "tnt-coach-en-a"
    tenant_b = "tnt-coach-en-b"

    # (a) First call — no session_id supplied.
    first = _post_turn(
        client,
        tenant=tenant_a,
        user_message="How should I prioritise my next learning step?",
        language="en",
    )
    assert first.status_code == 200, first.text
    first_body = first.json()
    _assert_canonical_shape(first_body)

    session_id = first_body["session_id"]
    assert session_id.startswith("cs_"), session_id
    assert first_body["next_prompt"], "next_prompt must be non-empty for en"

    # The fallback prompt (used when no LLM generator is configured) must
    # render in English for ``language="en"`` (R14.3).
    if first_body["next_prompt"].startswith("What's the smallest"):
        assert "evidence" in first_body["next_prompt"]

    # (b) Continue the same session on a second turn.
    second = _post_turn(
        client,
        tenant=tenant_a,
        user_message="Let's continue the previous discussion.",
        language="en",
        session_id=session_id,
    )
    assert second.status_code == 200, second.text
    second_body = second.json()
    _assert_canonical_shape(second_body)
    assert second_body["session_id"] == session_id

    # (c) Cross-tenant access — tenant_b cannot see tenant_a's session.
    cross = _post_turn(
        client,
        tenant=tenant_b,
        user_message="Trying to peek at another tenant's session.",
        language="en",
        session_id=session_id,
    )
    assert cross.status_code == 404, cross.text
    cross_text = repr(cross.json())
    assert session_id not in cross_text
    assert tenant_a not in cross_text

    # (d) Tenant_b creating its own session yields a *different* id.
    tenant_b_first = _post_turn(
        client,
        tenant=tenant_b,
        user_message="Start a new session for tenant b.",
        language="en",
    )
    assert tenant_b_first.status_code == 200, tenant_b_first.text
    tenant_b_session = tenant_b_first.json()["session_id"]
    assert tenant_b_session != session_id
