"""Property-based test for the pending-review write contract.

Feature: expert-coaching-loop, Property 16: every successful write to a
new endpoint declares ``metadata.mode`` in
``{pending-review, dry-run, mock-safe}`` (R11.1, R11.2, R11.5).
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from hypothesis import given, settings, strategies as st

_ALLOWED_MODES = {"pending-review", "dry-run", "mock-safe"}
_TENANT = "tnt-pending-review-pbt"
_HEADERS = {"X-Tenant-ID": _TENANT, "X-User-ID": "alice"}


def test_property_16_pending_review_metadata_and_status(client: TestClient) -> None:
    """New write endpoints always carry a safe ``metadata.mode``."""

    @settings(max_examples=60, deadline=None)
    @given(
        message=st.text(
            alphabet=st.characters(min_codepoint=97, max_codepoint=122),
            min_size=1,
            max_size=40,
        ),
        result_class=st.sampled_from(["success", "partial", "fail"]),
    )
    def _check(message: str, result_class: str) -> None:
        # (a) coach/turn — appends a session state-log row.
        turn = client.post(
            "/api/v2/coach/turn",
            json={"user_message": message, "language": "en", "mode": "simple"},
            headers=_HEADERS,
        )
        assert turn.status_code == 200, turn.text
        assert turn.json()["metadata"]["mode"] in _ALLOWED_MODES

        # (b) experiments/{id}/review — writes experiment_reviews.
        review = client.post(
            "/api/v2/experiments/exp_pbt/review",
            json={
                "result_class": result_class,
                "key_metrics": [],
                "notes": "",
                "concept_ids": [],
            },
            headers=_HEADERS,
        )
        assert review.status_code == 200, review.text
        assert review.json()["metadata"]["mode"] in _ALLOWED_MODES

    _check()
