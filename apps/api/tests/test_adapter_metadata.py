"""Tests for ``apps.api.app.adapter_metadata.make_metadata`` (Task 1.7)."""

from __future__ import annotations

import pytest

from apps.api.app.adapter_metadata import ALLOWED_MODES, make_metadata


def test_mode_validation_rejects_unknown() -> None:
    with pytest.raises(ValueError) as exc:
        make_metadata(
            adapter="v2.coach.turn",
            source_system="apps:api",
            mode="rocketship",  # type: ignore[arg-type]
        )
    assert "rocketship" in str(exc.value)
    # The allowed list is mentioned so callers can self-correct without
    # consulting the docs.
    for allowed in ALLOWED_MODES:
        assert allowed in str(exc.value)


@pytest.mark.parametrize("mode", sorted(ALLOWED_MODES))
def test_each_allowed_mode_round_trips(mode: str) -> None:
    metadata = make_metadata(
        adapter="v2.test",
        source_system="apps:api",
        mode=mode,  # type: ignore[arg-type]
        read_only=False,
    )
    assert metadata.mode == mode
    assert metadata.adapter == "v2.test"
    assert metadata.source_system == "apps:api"
    assert metadata.read_only is False


def test_default_is_mock_safe_and_read_only() -> None:
    metadata = make_metadata(adapter="v2.smoke", source_system="apps:api")
    assert metadata.mode == "mock-safe"
    assert metadata.read_only is True
