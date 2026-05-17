"""Wire-test for the ``REALITY_OS_COACH_ENABLED`` dark-launch flag (Task 2.17).

Validates the rollout-plan AC:

* When the flag is ``false`` (the production default at T+0 per
  design.md "Dark-launch sequence"), every coach route returns
  HTTP 404 with an opaque body — indistinguishable from a missing
  resource (R10.6, R12.3).
* When the flag is ``true``, the same coach routes serve traffic
  normally: ``POST /coach/turn`` creates a session and the read /
  archive endpoints behave as designed.
* Rubric routes are *not* gated by ``COACH_ENABLED`` — they ride
  on their own admin path (Task 2.15) and stay reachable in either
  flag state.

The test flips the flag exclusively through ``monkeypatch.setenv`` so
the change is fully reverted between cases. ``feature_flags`` reads
``os.environ`` on every call (no module-level cache), so toggling the
env var is sufficient — no manual cache reset is needed.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _headers(tenant: str = "tnt-flag-coach", user: str = "alice") -> dict[str, str]:
    return {"X-Tenant-ID": tenant, "X-User-ID": user}


def _coach_turn_body() -> dict[str, object]:
    return {
        "user_message": "Probe the flag.",
        "language": "en",
        "mode": "professional",
    }


# ---------------------------------------------------------------------------
# AC: routes 404 when flag is off
# ---------------------------------------------------------------------------


def test_routes_404_when_flag_off(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Every coach route returns 404 when ``REALITY_OS_COACH_ENABLED=false``.

    The 404 body must be opaque — no leak that the feature exists at
    all (R10.6, R12.3). Rubric routes remain reachable because they
    are not gated by this flag.
    """

    monkeypatch.setenv("REALITY_OS_COACH_ENABLED", "false")

    # POST /api/v2/coach/turn
    turn = client.post(
        "/api/v2/coach/turn", json=_coach_turn_body(), headers=_headers()
    )
    assert turn.status_code == 404, turn.text
    assert turn.json() == {"detail": "not found"}

    # GET /api/v2/coach/sessions/{id} — id never reaches the repo because
    # the gate fires first; the response shape is identical to a missing
    # session under the owning tenant.
    get_session = client.get(
        "/api/v2/coach/sessions/cs_does-not-matter", headers=_headers()
    )
    assert get_session.status_code == 404, get_session.text
    assert get_session.json() == {"detail": "not found"}
    # Opaque body — no echo of the requested id.
    assert "cs_does-not-matter" not in repr(get_session.json())

    # POST /api/v2/coach/sessions/{id}/archive
    archive = client.post(
        "/api/v2/coach/sessions/cs_does-not-matter/archive", headers=_headers()
    )
    assert archive.status_code == 404, archive.text
    assert archive.json() == {"detail": "not found"}
    assert "cs_does-not-matter" not in repr(archive.json())

    # Rubric routes are NOT gated by COACH_ENABLED — they stay reachable.
    rubrics = client.get("/api/v2/rubrics", headers=_headers())
    assert rubrics.status_code == 200, rubrics.text
    assert rubrics.json()["metadata"]["adapter"] == "v2.rubrics.list"


# ---------------------------------------------------------------------------
# AC: routes active when flag is on
# ---------------------------------------------------------------------------


def test_routes_active_when_flag_on(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When the flag is on, every coach route serves traffic normally.

    * ``POST /coach/turn`` creates a session and returns 200.
    * ``GET /coach/sessions/{id}`` reads it back under the owning
      tenant.
    * ``POST /coach/sessions/{id}/archive`` archives it.
    * Cross-tenant access still returns 404 — the flag does not
      relax tenant isolation (R1.10, R12.3).
    """

    monkeypatch.setenv("REALITY_OS_COACH_ENABLED", "true")

    tenant_a = "tnt-flag-coach-on-a"
    tenant_b = "tnt-flag-coach-on-b"

    # POST /coach/turn → 200 + session_id.
    turn = client.post(
        "/api/v2/coach/turn",
        json=_coach_turn_body(),
        headers=_headers(tenant=tenant_a),
    )
    assert turn.status_code == 200, turn.text
    body = turn.json()
    session_id = body["session_id"]
    assert session_id.startswith("cs_")
    # Sanity-check the response declares the canonical adapter and
    # write mode (R11.5) — confirms we hit the real handler, not the
    # gate.
    assert body["metadata"]["adapter"] == "v2.coach.turn"
    assert body["metadata"]["mode"] == "pending-review"

    # GET /coach/sessions/{id} → 200 for the owning tenant.
    get_session = client.get(
        f"/api/v2/coach/sessions/{session_id}", headers=_headers(tenant=tenant_a)
    )
    assert get_session.status_code == 200, get_session.text
    assert get_session.json()["session"]["id"] == session_id

    # Cross-tenant GET → 404 (tenant isolation still in force).
    cross = client.get(
        f"/api/v2/coach/sessions/{session_id}", headers=_headers(tenant=tenant_b)
    )
    assert cross.status_code == 404, cross.text
    cross_text = repr(cross.json())
    assert session_id not in cross_text
    assert tenant_a not in cross_text

    # POST /coach/sessions/{id}/archive → 200 for the owning tenant.
    archive = client.post(
        f"/api/v2/coach/sessions/{session_id}/archive",
        headers=_headers(tenant=tenant_a),
    )
    assert archive.status_code == 200, archive.text
    assert archive.json()["session"]["state"] == "archived"
