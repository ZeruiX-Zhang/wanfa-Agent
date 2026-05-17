"""Tests for the startup misconfiguration guard (Task 1.9 / R15.1, R15.3)."""

from __future__ import annotations

import pytest

from apps.api import main as main_mod
from apps.api.app.audit_events import SYSTEM_MISCONFIGURATION
from apps.api.app.feature_flags import detect_client_secret_leaks


def test_detect_works_with_no_leaks() -> None:
    env = {
        "REALITY_OS_API_KEY": "sk-secret",
        "NEXT_PUBLIC_API_BASE_URL": "https://example.com",
    }
    assert detect_client_secret_leaks(env) == []


def test_detect_flags_secret_mirror() -> None:
    env = {
        "REALITY_OS_API_KEY": "sk-secret",
        "NEXT_PUBLIC_API_KEY_LEAK": "sk-secret",
    }
    leaks = detect_client_secret_leaks(env)
    assert leaks
    assert "NEXT_PUBLIC_API_KEY_LEAK" in leaks[0]
    # Secret value must NOT appear in the leak description (R15.3 redaction).
    assert "sk-secret" not in leaks[0]


def test_startup_refuses_when_secret_exposed() -> None:
    """The guard raises when a leak is present and emits a redacted audit row."""

    leaky_env = {
        "REALITY_OS_API_KEY": "sk-startup-secret",
        "NEXT_PUBLIC_KIRO_LEAK": "sk-startup-secret",
    }

    audit_count_before = len(main_mod.storage.list_audit("system"))

    with pytest.raises(RuntimeError) as exc_info:
        main_mod._enforce_server_only_secrets(leaky_env)

    message = str(exc_info.value)
    assert "refused to start" in message
    assert "NEXT_PUBLIC_KIRO_LEAK" in message
    assert "sk-startup-secret" not in message  # redaction enforced

    audits_after = main_mod.storage.list_audit("system")
    assert len(audits_after) == audit_count_before + 1
    last = audits_after[-1]
    assert last.event_type == SYSTEM_MISCONFIGURATION
    assert last.action == "client_secret_leak"
    # Audit metadata also redacts the secret value.
    metadata_str = str(last.metadata)
    assert "NEXT_PUBLIC_KIRO_LEAK" in metadata_str
    assert "sk-startup-secret" not in metadata_str


def test_startup_passes_when_no_leak() -> None:
    """No leak → guard returns silently and emits no audit row."""

    audit_count_before = len(main_mod.storage.list_audit("system"))
    main_mod._enforce_server_only_secrets({"REALITY_OS_API_KEY": "sk", "OTHER": "x"})
    audit_count_after = len(main_mod.storage.list_audit("system"))
    assert audit_count_after == audit_count_before
