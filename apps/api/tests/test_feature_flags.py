"""Tests for ``apps.api.app.feature_flags`` (Task 1.4)."""

from __future__ import annotations

import pytest

from apps.api.app import feature_flags


@pytest.fixture(autouse=True)
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "REALITY_OS_COACH_ENABLED",
        "REALITY_OS_EXPERT_GAP_ENABLED",
        "REALITY_OS_HYBRID_RETRIEVAL",
        "REALITY_OS_COACH_AUTOSWITCH",
        "REALITY_OS_EMBED_MODE",
        "REALITY_OS_VECTOR_STORE",
        "REALITY_OS_COACH_IDLE_DAYS",
        "REALITY_OS_CALIBRATION_THRESHOLD",
        "REALITY_OS_CONSECUTIVE_FAIL_THRESHOLD",
        "REALITY_OS_API_KEY",
        "REALITY_OS_SERVER_API_KEY",
        "NEXT_PUBLIC_API_KEY_SAMPLE",
    ):
        monkeypatch.delenv(name, raising=False)


def test_defaults_all_off() -> None:
    """Every gate defaults to off so a fresh deploy changes no behaviour."""

    assert feature_flags.coach_enabled() is False
    assert feature_flags.expert_gap_enabled() is False
    assert feature_flags.hybrid_retrieval_enabled() is False
    assert feature_flags.coach_autoswitch() is False
    assert feature_flags.embed_mode() == "disabled"
    assert feature_flags.vector_store() == "sqlite_tfidf"
    assert feature_flags.coach_idle_days() == 30
    assert feature_flags.calibration_threshold() == pytest.approx(0.6)
    assert feature_flags.consecutive_fail_threshold() == 3


@pytest.mark.parametrize(
    "raw,expected",
    [("1", True), ("true", True), ("yes", True), ("ON", True), ("Y", True),
     ("0", False), ("false", False), ("no", False), ("OFF", False),
     ("", False), ("garbage", False)],
)
def test_bool_parsing(monkeypatch: pytest.MonkeyPatch, raw: str, expected: bool) -> None:
    monkeypatch.setenv("REALITY_OS_COACH_ENABLED", raw)
    assert feature_flags.coach_enabled() is expected


def test_embed_mode_validates_enum(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REALITY_OS_EMBED_MODE", "online")
    assert feature_flags.embed_mode() == "online"
    monkeypatch.setenv("REALITY_OS_EMBED_MODE", "OFFLINE")
    assert feature_flags.embed_mode() == "offline"
    monkeypatch.setenv("REALITY_OS_EMBED_MODE", "rocketship")
    assert feature_flags.embed_mode() == "disabled"  # unknown -> safe default


def test_calibration_threshold_bounds(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REALITY_OS_CALIBRATION_THRESHOLD", "0.42")
    assert feature_flags.calibration_threshold() == pytest.approx(0.42)
    monkeypatch.setenv("REALITY_OS_CALIBRATION_THRESHOLD", "5")
    assert feature_flags.calibration_threshold() == pytest.approx(0.6)  # clamped
    monkeypatch.setenv("REALITY_OS_CALIBRATION_THRESHOLD", "abc")
    assert feature_flags.calibration_threshold() == pytest.approx(0.6)


def test_idle_days_bounds(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REALITY_OS_COACH_IDLE_DAYS", "7")
    assert feature_flags.coach_idle_days() == 7
    monkeypatch.setenv("REALITY_OS_COACH_IDLE_DAYS", "0")
    assert feature_flags.coach_idle_days() == 30  # rejected -> default
    monkeypatch.setenv("REALITY_OS_COACH_IDLE_DAYS", "1000")
    assert feature_flags.coach_idle_days() == 30


def test_detect_client_secret_leaks_returns_empty_when_no_leak() -> None:
    env = {
        "REALITY_OS_API_KEY": "sk-abc",
        "NEXT_PUBLIC_API_BASE_URL": "https://example.com",
    }
    assert feature_flags.detect_client_secret_leaks(env) == []


def test_detect_client_secret_leaks_flags_mirror() -> None:
    env = {
        "REALITY_OS_API_KEY": "sk-abc",
        "NEXT_PUBLIC_API_KEY_SAMPLE": "sk-abc",  # leaked into client bundle
    }
    leaks = feature_flags.detect_client_secret_leaks(env)
    assert leaks == ["NEXT_PUBLIC_API_KEY_SAMPLE mirrors REALITY_OS_API_KEY"]


def test_detect_client_secret_leaks_does_not_echo_secret_value() -> None:
    secret = "super-sensitive-key-DO-NOT-LEAK"
    env = {
        "REALITY_OS_SERVER_API_KEY": secret,
        "NEXT_PUBLIC_OOPS": secret,
    }
    leaks = feature_flags.detect_client_secret_leaks(env)
    assert leaks
    assert all(secret not in entry for entry in leaks)
