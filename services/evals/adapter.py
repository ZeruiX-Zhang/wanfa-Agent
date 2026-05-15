"""Evaluation adapter for the smoke acceptance flow."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from services.verification import EvidenceState, VerificationAdapter


@dataclass(frozen=True)
class EvalCheck:
    """One smoke acceptance check."""

    name: str
    passed: bool
    detail: str

    def to_dict(self) -> dict[str, str | bool]:
        """Return a JSON-safe representation."""

        return {"name": self.name, "passed": self.passed, "detail": self.detail}


@dataclass(frozen=True)
class EvalSummary:
    """Summary for an acceptance flow evaluation."""

    flow_id: str
    passed: bool
    score: float
    checks: tuple[EvalCheck, ...]
    adapter_mode: str = "mock-safe"
    warnings: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-safe representation."""

        return {
            "flow_id": self.flow_id,
            "passed": self.passed,
            "score": self.score,
            "adapter_mode": self.adapter_mode,
            "checks": [check.to_dict() for check in self.checks],
            "warnings": list(self.warnings),
        }


class EvalAdapter:
    """Deterministic eval adapter for the acceptance path."""

    def __init__(self, verification_adapter: VerificationAdapter | None = None) -> None:
        self._verification = verification_adapter or VerificationAdapter()

    def build_smoke_acceptance_data(self) -> dict[str, object]:
        """Build a mock-safe end-to-end acceptance flow fixture."""

        flow: dict[str, object] = {
            "flow_id": "eval-smoke",
            "adapter_mode": "mock-safe",
            "user_input": "Should Reality OS keep knowledge writes pending review by default?",
            "clarification": {
                "clarified_problem": (
                    "Decide whether generated knowledge writes should be held for review "
                    "before entering the formal knowledge base."
                ),
                "questions": [
                    "Which knowledge stores are in scope?",
                    "Who can approve promotion from pending to formal knowledge?",
                ],
            },
            "retrieval": {
                "query": "Reality OS pending review knowledge write policy",
                "results": [
                    {
                        "id": "evidence-pending-review-policy",
                        "title": "Reality OS knowledge safety fixture",
                        "snippet": (
                            "Reality OS knowledge writes remain pending review by default "
                            "and can be undone before promotion."
                        ),
                        "source_uri": "mock://acceptance/pending-review-policy",
                        "source_type": "mock-safe-fixture",
                        "trust": "mock-safe",
                        "score": 0.92,
                    }
                ],
                "trace": [
                    {
                        "name": "retrieval",
                        "status": "mock_safe",
                        "detail": "Static smoke evidence projected without calling the RAG pipeline.",
                        "metadata": {"result_count": 1},
                    }
                ],
            },
            "memo": {
                "id": "memo-eval-smoke",
                "decision": "Keep generated knowledge writes pending review by default.",
                "claims": [
                    {
                        "id": "claim-pending-review-default",
                        "text": "Reality OS knowledge writes remain pending review by default.",
                        "source": "decision_memo",
                    }
                ],
                "counterarguments": [
                    "Pending review adds operational latency before knowledge can be reused."
                ],
                "risks": [
                    "Approvers may become a bottleneck if review queues are not monitored."
                ],
            },
        }

        verification = self._verification.verify_memo(
            memo=self._expect_mapping(flow["memo"]),
            retrieval_payload=self._expect_mapping(flow["retrieval"]),
        )
        flow["verification"] = verification.to_dict()
        flow["eval_summary"] = self.summarize_acceptance_flow(flow).to_dict()
        return flow

    def summarize_acceptance_flow(self, flow: Mapping[str, Any]) -> EvalSummary:
        """Evaluate whether a flow exposes required acceptance artifacts."""

        flow_id = str(flow.get("flow_id") or "unknown-flow")
        verification = self._mapping_or_empty(flow.get("verification"))
        memo = self._mapping_or_empty(flow.get("memo"))
        retrieval = self._mapping_or_empty(flow.get("retrieval"))
        clarification = self._mapping_or_empty(flow.get("clarification"))

        checks = (
            self._check_user_input(flow),
            self._check_clarification(clarification),
            self._check_retrieval(retrieval),
            self._check_memo_claims(memo),
            self._check_claim_evidence_binding(verification),
            self._check_confidence(verification),
            self._check_insufficient_evidence_state_available(verification),
        )
        passed_count = sum(1 for check in checks if check.passed)
        score = round(passed_count / len(checks), 3)
        warnings = self._warnings_from_verification(verification)
        return EvalSummary(
            flow_id=flow_id,
            passed=all(check.passed for check in checks),
            score=score,
            checks=checks,
            warnings=warnings,
        )

    def summarize_verification_report(self, report: Mapping[str, Any]) -> EvalSummary:
        """Evaluate a standalone verification report."""

        flow = {
            "flow_id": "verification-report",
            "user_input": "standalone verification",
            "clarification": {"clarified_problem": "standalone verification"},
            "retrieval": {"results": report.get("evidence", ())},
            "memo": {"claims": report.get("claims", ())},
            "verification": report,
        }
        return self.summarize_acceptance_flow(flow)

    def _check_user_input(self, flow: Mapping[str, Any]) -> EvalCheck:
        user_input = flow.get("user_input")
        passed = isinstance(user_input, str) and bool(user_input.strip())
        return EvalCheck(
            name="user_input",
            passed=passed,
            detail="User input is present." if passed else "Missing user input.",
        )

    def _check_clarification(self, clarification: Mapping[str, Any]) -> EvalCheck:
        has_problem = bool(str(clarification.get("clarified_problem") or "").strip())
        questions = clarification.get("questions")
        has_questions = isinstance(questions, Sequence) and not isinstance(questions, str) and bool(questions)
        passed = has_problem or has_questions
        return EvalCheck(
            name="clarification",
            passed=passed,
            detail="Clarification artifact is present." if passed else "Missing clarification artifact.",
        )

    def _check_retrieval(self, retrieval: Mapping[str, Any]) -> EvalCheck:
        evidence = retrieval.get("evidence") or retrieval.get("results") or retrieval.get("sources")
        count = len(evidence) if isinstance(evidence, Sequence) and not isinstance(evidence, str) else 0
        return EvalCheck(
            name="retrieval",
            passed=count > 0,
            detail=f"Retrieval exposes {count} evidence item(s).",
        )

    def _check_memo_claims(self, memo: Mapping[str, Any]) -> EvalCheck:
        claims = memo.get("claims")
        count = len(claims) if isinstance(claims, Sequence) and not isinstance(claims, str) else 0
        return EvalCheck(
            name="memo_claim",
            passed=count > 0,
            detail=f"Memo exposes {count} claim(s).",
        )

    def _check_claim_evidence_binding(self, verification: Mapping[str, Any]) -> EvalCheck:
        bindings = verification.get("bindings")
        count = len(bindings) if isinstance(bindings, Sequence) and not isinstance(bindings, str) else 0
        return EvalCheck(
            name="claim_evidence_binding",
            passed=count > 0,
            detail=f"Verification exposes {count} claim-to-evidence binding(s).",
        )

    def _check_confidence(self, verification: Mapping[str, Any]) -> EvalCheck:
        confidence = verification.get("confidence")
        if not isinstance(confidence, Sequence) or isinstance(confidence, str) or not confidence:
            return EvalCheck(name="confidence", passed=False, detail="Missing confidence records.")

        states = {
            str(item.get("state"))
            for item in confidence
            if isinstance(item, Mapping) and item.get("state") is not None
        }
        has_scores = all(
            isinstance(item, Mapping) and isinstance(item.get("score"), (float, int))
            for item in confidence
        )
        passed = has_scores and EvidenceState.SUPPORTED.value in states
        return EvalCheck(
            name="confidence",
            passed=passed,
            detail=f"Confidence states: {', '.join(sorted(states)) or 'none'}.",
        )

    def _check_insufficient_evidence_state_available(self, verification: Mapping[str, Any]) -> EvalCheck:
        known_states = {
            EvidenceState.SUPPORTED.value,
            EvidenceState.INSUFFICIENT_EVIDENCE.value,
            EvidenceState.UNVERIFIABLE.value,
            EvidenceState.CONFLICTED.value,
        }
        confidence = verification.get("confidence")
        if not isinstance(confidence, Sequence) or isinstance(confidence, str):
            observed_states: set[str] = set()
        else:
            observed_states = {
                str(item.get("state"))
                for item in confidence
                if isinstance(item, Mapping) and item.get("state") is not None
            }
        passed = observed_states.issubset(known_states)
        return EvalCheck(
            name="unverifiable_or_insufficient_state",
            passed=passed,
            detail="Verification states are normalized." if passed else "Unknown verification state present.",
        )

    def _warnings_from_verification(self, verification: Mapping[str, Any]) -> tuple[str, ...]:
        warnings = verification.get("warnings")
        if not isinstance(warnings, Sequence) or isinstance(warnings, str):
            return ()
        return tuple(str(warning) for warning in warnings)

    def _mapping_or_empty(self, value: object) -> Mapping[str, Any]:
        return value if isinstance(value, Mapping) else {}

    def _expect_mapping(self, value: object) -> Mapping[str, Any]:
        if not isinstance(value, Mapping):
            raise TypeError("Expected mapping payload")
        return value
