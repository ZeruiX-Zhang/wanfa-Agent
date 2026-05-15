from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from .eval_harness import (
    assert_dataset_files_are_valid,
    install_evidence_snapshot_patch,
    load_jsonl,
    run_audit_case,
    run_orchestrator_case,
    run_rag_case,
    run_thinking_router_case,
)


def _case_id(case: dict[str, object]) -> str:
    return str(case["id"])


@pytest.fixture(autouse=True)
def _patch_missing_snapshot_helper(monkeypatch: pytest.MonkeyPatch) -> None:
    install_evidence_snapshot_patch(monkeypatch)


def test_p0_5_golden_dataset_files_are_valid() -> None:
    assert_dataset_files_are_valid()


@pytest.mark.parametrize("case", load_jsonl("rag_basic.jsonl"), ids=_case_id)
def test_p0_5_golden_rag_basic(client: TestClient, case: dict[str, object]) -> None:
    run_rag_case(client, case)


@pytest.mark.parametrize("case", load_jsonl("thinking_router.jsonl"), ids=_case_id)
def test_p0_5_golden_thinking_router(client: TestClient, case: dict[str, object]) -> None:
    run_thinking_router_case(client, case)


@pytest.mark.parametrize("case", load_jsonl("audit_security.jsonl"), ids=_case_id)
def test_p0_5_golden_audit_security(client: TestClient, case: dict[str, object]) -> None:
    run_audit_case(client, case)


@pytest.mark.parametrize("case", load_jsonl("orchestrator_cases.jsonl"), ids=_case_id)
def test_p0_5_golden_orchestrator(client: TestClient, case: dict[str, object]) -> None:
    run_orchestrator_case(client, case)
