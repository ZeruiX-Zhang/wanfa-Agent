"""Unit tests for ``apps.api.app.mastery`` helpers (Task 3.2)."""

from __future__ import annotations

import pytest

from apps.api.app.mastery import grade_to_sm2


def test_grade_to_sm2_mapping() -> None:
    """`grade_to_sm2` maps result_class to the SM-2 grade per R9.2."""

    assert grade_to_sm2("success") == 5
    assert grade_to_sm2("partial") == 3
    assert grade_to_sm2("fail") == 1

    with pytest.raises(ValueError):
        grade_to_sm2("unknown")  # type: ignore[arg-type]
