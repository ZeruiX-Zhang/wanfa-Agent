"""Integration tests for ``GET /api/v2/coach/sessions/{id}`` and
``POST /api/v2/coach/sessions/{id}/archive`` (Task 2.14).

Validates Requirements:

* **R1.7** — archived sessions are still readable via ``GET`` but
  subsequent ``POST /api/v2/coach/turn`` writes against an archived
  session are rejected with HTTP 409.
* **R12.3** — cross-tenant reads/writes return HTTP 404 with no
  metadata leakage (the response body must not echo the requested
  ``session_id`` or the originating tenant id).
* **R11.5** — the ``archive`` write path declares
  ``metadata.mode = "pending-review"`` because it appends a
  ``coaching_session_state_log`` row, while the ``GET`` read path
  declares ``metadata.mode = "read-only"``.
* **R13.1 / R13.4** — archiving emits a ``coaching_session_transition``
  audit row *and* a ``coaching_session.archived`` audit row.
"""

from __future__ import annotations

import json
from typing import Any

from fastapi.testclient import TestClient

from apps.api.app.coaching_session import CoachingSessionRepo
from apps.api.app.knowledge_core import default_core_path


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _create_session(client: TestClient, *, tenant: str, user: str = "alice") -> str:
    """Drive ``POST /coach/turn`` once to seed a session and return its id."""

    response = client.post(
        "/api/v2/coach/turn",
        json={
            "user_message": "Seed a session for tests.",
            "language": "en",
            "mode": "professional",
        },
        headers={"X-Tenant-ID": tenant, "X-User-ID": user},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    session_id = body["session_id"]
    assert session_id.startswith("cs_"), session_id
    return session_id


def _audit_rows_for_session(*, tenant_id: str, session_id: str) -> list[dict[str, Any]]:
    """Read the on-disk audit_log rows scoped to one tenant + session."""

    repo = CoachingSessionRepo(path=default_core_path())
    with repo._connect() as db:  # type: ignore[attr-defined]
        rows = db.execute(
            "select id, action, subject, payload_json, created_at "
            "from audit_log where tenant_id = ? and subject = ? "
            "order by created_at asc",
            (tenant_id, session_id),
        ).fetchall()
    return [dict(row) for row in rows]


# ---------------------------------------------------------------------------
# GET /api/v2/coach/sessions/{id} — tenant scoping (R1.7, R12.3)
# ---------------------------------------------------------------------------


def test_get_session_tenant_scoped(client: TestClient) -> None:
    """Read access is allowed for the owning tenant; cross-tenant returns 404.

    Steps:

    1. Tenant A creates a session via ``POST /coach/turn``.
    2. Tenant A's ``GET /coach/sessions/{id}`` returns the same
       aggregate. ``metadata.mode`` is ``"read-only"`` (R11.5).
    3. Tenant B's ``GET /coach/sessions/{id}`` returns ``404`` with no
       leakage of the session id or tenant A's tenant id (R12.3,
       R10.6).
    """

    tenant_a = "tnt-coach-get-a"
    tenant_b = "tnt-coach-get-b"

    session_id = _create_session(client, tenant=tenant_a)

    # (1) Tenant A reads its own session.
    response = client.get(
        f"/api/v2/coach/sessions/{session_id}",
        headers={"X-Tenant-ID": tenant_a, "X-User-ID": "alice"},
    )
    assert response.status_code == 200, response.text
    body = response.json()

    # Response carries the documented top-level keys.
    assert "metadata" in body and "session" in body
    assert body["metadata"]["adapter"] == "v2.coach.sessions.get"
    assert body["metadata"]["mode"] == "read-only"  # R11.5
    assert body["metadata"]["read_only"] is True

    session = body["session"]
    assert session["id"] == session_id
    assert session["tenant_id"] == tenant_a
    assert session["state"] in {
        "active",
        "awaiting_evidence",
        "awaiting_practice",
        "awaiting_experiment",
        "awaiting_review",
        "paused",
        "archived",
    }

    # (2) Tenant B asks about tenant A's session — must be 404 with no
    # information about whether the session exists or which tenant owns
    # it (R1.10, R12.3, R10.6).
    cross = client.get(
        f"/api/v2/coach/sessions/{session_id}",
        headers={"X-Tenant-ID": tenant_b, "X-User-ID": "mallory"},
    )
    assert cross.status_code == 404, cross.text
    cross_text = repr(cross.json())
    assert session_id not in cross_text
    assert tenant_a not in cross_text


# ---------------------------------------------------------------------------
# POST /api/v2/coach/sessions/{id}/archive — audit + write-reject (R1.7, R13)
# ---------------------------------------------------------------------------


def test_archive_session_writes_audit(client: TestClient) -> None:
    """Archiving a session transitions to ``archived``, emits the right
    audit events, and any follow-up coach turn against the archived
    session is rejected with HTTP 409.

    Validates:

    * Response body: ``session.state == "archived"`` and
      ``metadata.mode == "pending-review"`` (R11.5).
    * Audit log: at least one ``coaching_session_transition`` row and
      one ``coaching_session.archived`` row (R13.1, R13.4).
    * R1.7 (write-reject): a follow-up ``POST /coach/turn`` against the
      archived session id returns ``409``.
    * Cross-tenant archive returns ``404`` with no leakage (R12.3).
    * Already-archived returns ``409`` (design.md "Endpoint × mode"
      table — explicit conflict).
    """

    tenant_a = "tnt-coach-arc-a"
    tenant_b = "tnt-coach-arc-b"

    session_id = _create_session(client, tenant=tenant_a)

    # (1) Cross-tenant archive must 404 *before* a successful archive
    # so we can prove the 404 is not "already archived" leaking through.
    cross_archive = client.post(
        f"/api/v2/coach/sessions/{session_id}/archive",
        headers={"X-Tenant-ID": tenant_b, "X-User-ID": "mallory"},
    )
    assert cross_archive.status_code == 404, cross_archive.text
    cross_text = repr(cross_archive.json())
    assert session_id not in cross_text
    assert tenant_a not in cross_text

    # (2) Tenant A archives its own session.
    archive_response = client.post(
        f"/api/v2/coach/sessions/{session_id}/archive",
        headers={"X-Tenant-ID": tenant_a, "X-User-ID": "alice"},
    )
    assert archive_response.status_code == 200, archive_response.text
    body = archive_response.json()

    # Response shape: declared mode and archived state.
    assert body["metadata"]["adapter"] == "v2.coach.sessions.archive"
    assert body["metadata"]["mode"] == "pending-review"  # R11.5
    assert body["metadata"]["read_only"] is False
    assert body["session"]["state"] == "archived"
    assert body["session"]["archived_at"] is not None

    # (3) Audit rows: a transition row and an archived row, both scoped
    # to the same tenant + session (R13.1, R13.4).
    rows = _audit_rows_for_session(tenant_id=tenant_a, session_id=session_id)
    actions = [row["action"] for row in rows]
    assert "coaching_session_transition" in actions, actions
    assert "coaching_session.archived" in actions, actions

    # The transition payload should record the right from/to states.
    transition_rows = [
        row for row in rows if row["action"] == "coaching_session_transition"
    ]
    last_transition = transition_rows[-1]
    payload = json.loads(last_transition["payload_json"])
    assert payload["to_state"] == "archived"
    assert payload["session_id"] == session_id
    # Audit metadata stays redacted-by-default (R13.5).
    assert payload.get("redacted") is True

    # (4) GET still works on the archived session (R1.7 read-allow).
    get_after_archive = client.get(
        f"/api/v2/coach/sessions/{session_id}",
        headers={"X-Tenant-ID": tenant_a, "X-User-ID": "alice"},
    )
    assert get_after_archive.status_code == 200, get_after_archive.text
    assert get_after_archive.json()["session"]["state"] == "archived"

    # (5) Follow-up coach turn against the archived session must be
    # rejected with HTTP 409 (R1.7 write-reject).
    follow_up_turn = client.post(
        "/api/v2/coach/turn",
        json={
            "session_id": session_id,
            "user_message": "Try to keep going against an archived session.",
            "language": "en",
            "mode": "professional",
        },
        headers={"X-Tenant-ID": tenant_a, "X-User-ID": "alice"},
    )
    assert follow_up_turn.status_code == 409, follow_up_turn.text

    # (6) Re-archiving must return 409 (idempotency-via-conflict per
    # design.md).
    re_archive = client.post(
        f"/api/v2/coach/sessions/{session_id}/archive",
        headers={"X-Tenant-ID": tenant_a, "X-User-ID": "alice"},
    )
    assert re_archive.status_code == 409, re_archive.text
