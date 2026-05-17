"""Integration test — full coach turn loop end-to-end (Task 6.8).

Covers R1.3 and R14.2-3: a multi-turn coaching session runs the complete
loop (turn -> state transition -> next_action -> metacognition) in both
the zh-CN and en locales.
"""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

_VALID_STATES = {
    "active",
    "awaiting_evidence",
    "awaiting_practice",
    "awaiting_experiment",
    "awaiting_review",
    "paused",
    "archived",
}
_VALID_ACTIONS = {"learn", "practice", "experiment", "review", "awaiting_evidence"}


def _assert_turn_shape(body: dict[str, Any]) -> None:
    for key in (
        "metadata",
        "session_id",
        "session_state",
        "next_prompt",
        "next_action",
        "metacognition",
        "audit_id",
        "run_id",
    ):
        assert key in body, f"missing coach-turn key: {key!r}"
    assert body["metadata"]["mode"] == "pending-review"
    assert body["session_state"] in _VALID_STATES
    assert body["next_action"] in _VALID_ACTIONS
    assert body["next_prompt"], "next_prompt must be non-empty"
    assert body["audit_id"], "every turn records an audit id"


def _run_loop(client: TestClient, *, tenant: str, language: str, messages: list[str]):
    session_id: str | None = None
    for turn_index, message in enumerate(messages):
        payload: dict[str, Any] = {
            "user_message": message,
            "language": language,
            "mode": "professional",
            "confidence_check": 0.5,
        }
        if session_id is not None:
            payload["session_id"] = session_id
        response = client.post(
            "/api/v2/coach/turn",
            json=payload,
            headers={"X-Tenant-ID": tenant, "X-User-ID": "alice"},
        )
        assert response.status_code == 200, response.text
        body = response.json()
        _assert_turn_shape(body)

        if session_id is None:
            session_id = body["session_id"]
            assert session_id.startswith("cs_")
        else:
            # Every later turn continues the same persisted session (R1.8).
            assert body["session_id"] == session_id

        # Professional_Mode surfaces a metacognition block every turn.
        metacog = body["metacognition"]
        assert metacog is not None
        assert metacog["user_confidence"] == 0.5

    assert session_id is not None

    # The session is readable after the loop completes (R1.7).
    final = client.get(
        f"/api/v2/coach/sessions/{session_id}",
        headers={"X-Tenant-ID": tenant, "X-User-ID": "alice"},
    )
    assert final.status_code == 200, final.text
    return session_id


def test_coach_e2e_zhCN_full_loop(client: TestClient) -> None:
    _run_loop(
        client,
        tenant="tnt-coach-e2e-zh",
        language="zh-CN",
        messages=[
            "我想系统地评估这个决策。",
            "继续上一轮，补充更多背景。",
            "现在帮我总结下一步该做什么。",
        ],
    )


def test_coach_e2e_en_full_loop(client: TestClient) -> None:
    _run_loop(
        client,
        tenant="tnt-coach-e2e-en",
        language="en",
        messages=[
            "I want to evaluate this decision systematically.",
            "Continue from the last turn with more context.",
            "Now help me summarise what to do next.",
        ],
    )
