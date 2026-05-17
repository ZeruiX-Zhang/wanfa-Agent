"""Property-based test for tenant isolation.

Feature: expert-coaching-loop, Property 5: any cross-tenant read of a
coaching session returns HTTP 404 with no metadata leakage (R1.10,
R12.2-4, R10.6).
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from hypothesis import assume, given, settings, strategies as st

_OWNER = "tnt-iso-owner"


def test_property_5_cross_tenant_returns_404(client: TestClient) -> None:
    """A session created under one tenant is invisible to every other."""

    created = client.post(
        "/api/v2/coach/turn",
        json={"user_message": "isolate me", "language": "en", "mode": "simple"},
        headers={"X-Tenant-ID": _OWNER, "X-User-ID": "alice"},
    )
    assert created.status_code == 200, created.text
    session_id = created.json()["session_id"]

    # The owner can still read its own session — a control assertion.
    own = client.get(
        f"/api/v2/coach/sessions/{session_id}",
        headers={"X-Tenant-ID": _OWNER, "X-User-ID": "alice"},
    )
    assert own.status_code == 200, own.text

    @settings(max_examples=80, deadline=None)
    @given(
        other_tenant=st.text(
            alphabet=st.characters(min_codepoint=97, max_codepoint=122),
            min_size=1,
            max_size=24,
        )
    )
    def _check(other_tenant: str) -> None:
        assume(other_tenant != _OWNER)

        response = client.get(
            f"/api/v2/coach/sessions/{session_id}",
            headers={"X-Tenant-ID": other_tenant, "X-User-ID": "mallory"},
        )
        assert response.status_code == 404
        # The 404 body leaks neither the session id nor the owner tenant.
        body = repr(response.json())
        assert session_id not in body
        assert _OWNER not in body

    _check()
