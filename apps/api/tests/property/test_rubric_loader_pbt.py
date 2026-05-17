"""Property-based tests for the Expert Rubric loader.

Feature: expert-coaching-loop, Property 7: Rubric loader robustness
Validates: Requirements 2.5, 2.6, 2.7
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from hypothesis import HealthCheck, given, settings, strategies as st

from apps.api.app import expert_rubric


@pytest.fixture(autouse=True)
def fresh_cache() -> None:
    expert_rubric.reset_cache_for_tests()
    expert_rubric.load_all(refresh=True)


_required_field = st.sampled_from(["version", "author", "source", "domain"])


@settings(max_examples=40, deadline=None)
@given(missing=_required_field)
def test_property_7_loader_refuses_missing_required_field(
    tmp_path_factory: pytest.TempPathFactory, missing: str
) -> None:
    payload = {
        "domain": "rubric_pbt_domain",
        "version": "0.1.0",
        "author": "tester",
        "source": "tests",
        "cited_evidence_ids": [],
        "dimensions": [
            {"id": "x", "weight": 1.0, "anchors": ["alpha"]},
        ],
    }
    payload.pop(missing)
    path = tmp_path_factory.mktemp("rubric") / "bad.yaml"
    path.write_text(yaml.safe_dump(payload), encoding="utf-8")

    result = expert_rubric.load_rubric_file(path)
    assert result.rubric is None
    assert result.status == "refused"
    assert missing in (result.refused_reason or "")


def test_property_7_loader_refuses_unresolved_evidence_ids(tmp_path: Path) -> None:
    payload = {
        "domain": "evidence_pbt",
        "version": "0.1.0",
        "author": "tester",
        "source": "tests",
        "cited_evidence_ids": ["ev_missing"],
        "dimensions": [{"id": "x", "weight": 1.0, "anchors": ["alpha"]}],
    }
    path = tmp_path / "evidence.yaml"
    path.write_text(yaml.safe_dump(payload), encoding="utf-8")

    def resolver(evidence_id: str) -> bool:
        return False  # nothing resolves

    result = expert_rubric.load_rubric_file(path, evidence_resolver=resolver)
    assert result.rubric is None
    assert "unresolved_evidence_ids" in (result.refused_reason or "")


def test_property_7_unknown_domain_falls_back_to_default() -> None:
    rubric, source = expert_rubric.resolve_rubric("never_registered_domain")
    assert source == "default"
    assert rubric is not None
    assert rubric.domain == "default"


def test_property_7_prior_versions_remain_readable(tmp_path: Path) -> None:
    """Loading version v2 keeps v1 readable for historical sessions (R2.6)."""

    def write(domain: str, version: str) -> Path:
        path = tmp_path / f"{domain}-{version}.yaml"
        payload = {
            "domain": domain,
            "version": version,
            "author": "tester",
            "source": "tests",
            "cited_evidence_ids": [],
            "dimensions": [{"id": "x", "weight": 1.0, "anchors": ["alpha"]}],
        }
        path.write_text(yaml.safe_dump(payload), encoding="utf-8")
        return path

    expert_rubric.reset_cache_for_tests()
    p1 = write("history_pbt", "1.0.0")
    expert_rubric.load_rubric_file(p1)  # populate cache via load_all instead

    expert_rubric.load_all(root=tmp_path, refresh=True)
    assert expert_rubric.list_versions("history_pbt") == ["1.0.0"]

    write("history_pbt", "2.0.0")
    expert_rubric.load_all(root=tmp_path, refresh=True)
    assert sorted(expert_rubric.list_versions("history_pbt")) == ["1.0.0", "2.0.0"]

    v1 = expert_rubric.get_rubric("history_pbt", version="1.0.0")
    v2 = expert_rubric.get_rubric("history_pbt", version="2.0.0")
    assert v1 is not None and v1.version == "1.0.0"
    assert v2 is not None and v2.version == "2.0.0"
