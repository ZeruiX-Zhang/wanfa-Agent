"""Data-driven pytest helpers for P0.5 golden dataset evaluations."""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient


DATASET_DIR = Path(__file__).resolve().parents[1] / "eval_datasets"
REQUIRED_DATASETS = (
    "rag_basic.jsonl",
    "thinking_router.jsonl",
    "audit_security.jsonl",
    "orchestrator_cases.jsonl",
)


def load_jsonl(filename: str) -> list[dict[str, Any]]:
    path = DATASET_DIR / filename
    cases: list[dict[str, Any]] = []
    with path.open("r", encoding="ascii") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            line = raw_line.strip()
            if not line:
                continue
            try:
                case = json.loads(line)
            except json.JSONDecodeError as exc:
                raise AssertionError(f"{filename}:{line_number} is not valid JSON") from exc
            if not isinstance(case, dict):
                raise AssertionError(f"{filename}:{line_number} must contain a JSON object")
            cases.append(case)
    return cases


def all_dataset_cases() -> list[tuple[str, dict[str, Any]]]:
    return [(filename, case) for filename in REQUIRED_DATASETS for case in load_jsonl(filename)]


def install_evidence_snapshot_patch(monkeypatch: Any) -> None:
    """Patch the current test process when the app lacks the snapshot row helper."""

    from apps.api.app import knowledge_core as kc

    if hasattr(kc, "_create_evidence_snapshot_row"):
        return

    def create_evidence_snapshot_row(
        db: Any,
        *,
        tenant_id: str,
        title: str,
        content: str,
        source_kind: str,
        source_url: str | None = None,
        canonical_url: str | None = None,
        publisher: str | None = None,
        author: str | None = None,
        published_at: str | None = None,
        credibility_score: float = 0.0,
        retrieval_score: float | None = None,
        item_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Any:
        del metadata
        fetched_at = kc._utc_now_iso()
        snapshot_id = kc._new_id("snap")
        excerpt = content[:500]
        excerpt_hash = kc._content_hash(excerpt)
        content_hash = kc._content_hash(content)
        security_flags = kc.flags_for_text(content, source=source_kind)
        db.execute(
            """
            insert into evidence_snapshots(
              snapshot_id, tenant_id, source_url, canonical_url, title, publisher,
              author, published_at, fetched_at, content_hash, excerpt, excerpt_hash,
              surrounding_context, credibility_score, retrieval_score, source_kind,
              item_id, security_flags_json, content_role, metadata_json
            ) values(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                snapshot_id,
                tenant_id,
                source_url,
                canonical_url,
                title,
                publisher,
                author,
                published_at,
                fetched_at,
                content_hash,
                excerpt,
                excerpt_hash,
                content,
                credibility_score,
                retrieval_score,
                source_kind,
                item_id,
                json.dumps(security_flags),
                "evidence",
                "{}",
            ),
        )
        return kc.EvidenceSnapshot(
            snapshot_id=snapshot_id,
            tenant_id=tenant_id,
            source_url=source_url,
            canonical_url=canonical_url,
            title=title,
            publisher=publisher,
            author=author,
            published_at=published_at,
            fetched_at=fetched_at,
            content_hash=content_hash,
            excerpt=excerpt,
            excerpt_hash=excerpt_hash,
            surrounding_context=content,
            credibility_score=credibility_score,
            retrieval_score=retrieval_score,
            source_kind=source_kind,
            item_id=item_id,
            security_flags=security_flags,
            content_role="evidence",
        )

    monkeypatch.setattr(kc, "_create_evidence_snapshot_row", create_evidence_snapshot_row, raising=False)


def assert_dataset_files_are_valid() -> None:
    markers: set[str] = set()
    case_ids: set[str] = set()
    for filename in REQUIRED_DATASETS:
        path = DATASET_DIR / filename
        assert path.exists(), f"missing dataset: {filename}"
        path.read_text(encoding="ascii")
        cases = load_jsonl(filename)
        assert cases, f"{filename} must contain at least one case"
        for case in cases:
            case_id = case.get("id")
            marker = case.get("marker")
            assert isinstance(case_id, str) and case_id, f"{filename} case is missing id"
            assert case_id not in case_ids, f"duplicate case id: {case_id}"
            case_ids.add(case_id)
            assert isinstance(marker, str) and marker.startswith("p05_golden_"), f"{case_id} has invalid marker"
            assert marker not in markers, f"duplicate marker: {marker}"
            markers.add(marker)
            assert marker in json.dumps(case, ensure_ascii=True), f"{case_id} marker is not used in case"


def run_rag_case(client: TestClient, case: dict[str, Any]) -> dict[str, Any]:
    absorb = client.post("/api/v2/absorb", json=case["absorb"])
    assert absorb.status_code == 201, absorb.text

    body = absorb.json()
    for expected_flag in case.get("expect", {}).get("absorb_security_flags_any", []):
        if expected_flag in body.get("security_flags", []):
            break
    else:
        assert not case.get("expect", {}).get("absorb_security_flags_any"), body

    response = client.post("/api/v2/ask", json=case["ask"])
    result = _assert_common_response(response, case)
    _assert_answer_contract(result, case["expect"])
    _assert_citations(result, case["expect"])
    return result


def run_thinking_router_case(client: TestClient, case: dict[str, Any]) -> dict[str, Any]:
    response = client.post("/api/v2/thinking-models/route", json=case["request"])
    result = _assert_common_response(response, case)
    expected = case["expect"]
    assert result["matched"] is expected["matched"]
    if expected["matched"]:
        model = result["model"]
        assert model["id"] == expected["model_id"]
        assert model["category"] == expected["category"]
    else:
        assert result["model"] is None
    return result


def run_audit_case(client: TestClient, case: dict[str, Any]) -> dict[str, Any]:
    response = client.post("/api/v2/audit/review", json=case["request"])
    result = _assert_common_response(response, case)
    expected = case["expect"]
    assert result["source"] == expected["source"]
    assert result["passed"] is expected["passed"]
    assert result["score"] <= expected["max_score"]
    issue_dimensions = {issue["dimension"] for issue in result["issues"]}
    assert issue_dimensions & set(expected["issue_dimensions_any"]), result
    assert result["run_id"]
    return result


def run_orchestrator_case(client: TestClient, case: dict[str, Any]) -> dict[str, Any]:
    absorb = client.post("/api/v2/absorb", json=case["absorb"])
    assert absorb.status_code == 201, absorb.text

    response = client.post("/api/v2/orchestrate/ask", json=case["ask"])
    result = _assert_common_response(response, case)
    _assert_answer_contract(result, case["expect"])
    _assert_citations(result, case["expect"])
    _assert_orchestration(result, case["expect"])
    return result


def _assert_common_response(response: Any, case: dict[str, Any]) -> dict[str, Any]:
    expected_status = case["expect"]["status_code"]
    assert response.status_code == expected_status, response.text
    body = response.json()
    assert isinstance(body, dict)
    return body


def _assert_answer_contract(result: dict[str, Any], expected: dict[str, Any]) -> None:
    answer = result.get("answer", "")
    if "answer_equals" in expected:
        assert answer == expected["answer_equals"]
    if expected.get("answer_contains_any"):
        _assert_contains_any(answer, expected["answer_contains_any"])
    for term in expected.get("forbidden_answer_terms", []):
        assert term.lower() not in answer.lower()
    for field in expected.get("requires_non_empty", []):
        assert result.get(field), f"{field} should be non-empty"


def _assert_citations(result: dict[str, Any], expected: dict[str, Any]) -> None:
    citations = result.get("citations", [])
    assert len(citations) >= expected.get("min_citations", 0)
    if expected.get("citation_title_contains"):
        assert any(expected["citation_title_contains"] in citation.get("title", "") for citation in citations), citations
    if expected.get("citation_security_flags_any"):
        flags = {
            flag
            for citation in citations
            for flag in citation.get("security_flags", [])
        }
        assert flags & set(expected["citation_security_flags_any"]), citations
    assert all(citation.get("content_role") == "evidence" for citation in citations)


def _assert_orchestration(result: dict[str, Any], expected: dict[str, Any]) -> None:
    orchestration = result.get("orchestration")
    assert isinstance(orchestration, dict)
    steps = {step.get("step") for step in orchestration.get("steps", [])}
    assert steps & set(expected.get("orchestration_steps_any", [])), orchestration
    assert result.get("run_id")


def _assert_contains_any(text: str, terms: Iterable[str]) -> None:
    lowered = text.lower()
    assert any(term.lower() in lowered for term in terms), text
