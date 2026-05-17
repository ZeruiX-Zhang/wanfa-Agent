"""Integration tests for metacognition in the coach turn (Task 4.2).

Covers Requirements 7.1, 7.2, 7.5, 7.6:

* R7.1/R7.3 — every prompting coach turn surfaces a metacognition block
  with 3--7 ``questions_you_didnt_ask``.
* R7.5 — the user/system confidence pair is persisted.
* R7.6 — Simple_Mode prompts at most once per UTC day per session;
  Professional_Mode prompts on every significant turn.
"""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient


def _post_turn(
    client: TestClient,
    *,
    tenant: str,
    user_message: str,
    mode: str,
    session_id: str | None = None,
    confidence_check: float | None = None,
) -> Any:
    body: dict[str, Any] = {
        "user_message": user_message,
        "language": "en",
        "mode": mode,
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


def test_coach_turn_emits_metacog_block(client: TestClient) -> None:
    """A Professional_Mode coach turn surfaces a populated metacog block."""

    tenant = "tnt-metacog-block"
    response = _post_turn(
        client,
        tenant=tenant,
        user_message="How should I weigh these two options?",
        mode="professional",
        confidence_check=0.6,
    )
    assert response.status_code == 200, response.text
    block = response.json()["metacognition"]
    assert block is not None

    # Professional_Mode prompts on every significant turn (R7.6).
    assert block["confidence_check_required"] is True

    # The confidence pair is carried through (R7.5).
    assert block["user_confidence"] == 0.6
    assert isinstance(block["system_confidence"], (int, float))

    # 3--7 questions the user did not ask (R7.3, Property 22).
    questions = block["questions_you_didnt_ask"]
    assert isinstance(questions, list)
    assert 3 <= len(questions) <= 7
    assert all(isinstance(q, str) and q for q in questions)


def test_simple_mode_one_prompt_per_day(client: TestClient) -> None:
    """Simple_Mode prompts once per UTC day per session, not twice."""

    tenant = "tnt-metacog-simple"

    # First turn in a fresh session -> prompt fires.
    first = _post_turn(
        client,
        tenant=tenant,
        user_message="What should I focus on next?",
        mode="simple",
        confidence_check=0.5,
    )
    assert first.status_code == 200, first.text
    first_body = first.json()
    session_id = first_body["session_id"]
    first_block = first_body["metacognition"]
    assert first_block is not None
    assert first_block["confidence_check_required"] is True
    assert 3 <= len(first_block["questions_you_didnt_ask"]) <= 7

    # Second turn, same session, same UTC day -> prompt suppressed.
    second = _post_turn(
        client,
        tenant=tenant,
        user_message="And after that?",
        mode="simple",
        session_id=session_id,
    )
    assert second.status_code == 200, second.text
    second_block = second.json()["metacognition"]
    assert second_block is not None
    assert second_block["confidence_check_required"] is False
    assert second_block["questions_you_didnt_ask"] == []
