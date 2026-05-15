from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from .models import CapturedInput, CaptureSource, ClarifiedProblem, KnowledgeOSSummary


EXTERNAL_SOURCE_KINDS = {
    "browser-extension",
    "webpage",
    "external-webpage",
    "file",
    "external-file",
    "upload",
}


def clarify_problem(payload: Mapping[str, Any] | str) -> dict[str, Any]:
    return PromptOrchestratorAdapter(persist_inputs=False).clarify(payload)


def capture_input(payload: Mapping[str, Any] | str) -> dict[str, Any]:
    return PromptOrchestratorAdapter(persist_inputs=False).capture(payload)


def knowledge_os_summary(payload: Mapping[str, Any] | None = None) -> dict[str, Any]:
    return PromptOrchestratorAdapter(persist_inputs=False).knowledge_summary(payload)


def build_prompt_adapter(
    storage_dir: str | Path | None = None,
    *,
    persist_inputs: bool = True,
) -> "PromptOrchestratorAdapter":
    return PromptOrchestratorAdapter(storage_dir=storage_dir, persist_inputs=persist_inputs)


class PromptOrchestratorAdapter:
    """Small, dependency-free Phase 5 prompt adapter.

    The adapter does not call an LLM and does not write to the formal knowledge
    base. Captured inputs are marked pending and untrusted by default.
    """

    def __init__(
        self,
        storage_dir: str | Path | None = None,
        *,
        persist_inputs: bool = True,
    ) -> None:
        self.storage_dir = Path(storage_dir) if storage_dir else Path(__file__).resolve().parents[1] / "data"
        self.persist_inputs = persist_inputs

    @property
    def pending_inputs_path(self) -> Path:
        return self.storage_dir / "pending_inputs.jsonl"

    def clarify(self, payload: Mapping[str, Any] | str) -> dict[str, Any]:
        data = _coerce_payload(payload, default_key="problem")
        original = _clean_text(data.get("problem") or data.get("text") or data.get("selected_text") or "")
        context = _clean_text(data.get("context") or "")
        goal = _clean_text(data.get("goal") or data.get("user_goal") or "")
        constraints = _listify(data.get("constraints"))

        normalized = _normalize_problem(original, goal)
        missing = _missing_information(original, context, goal, constraints)
        questions = _clarifying_questions(missing)
        assumptions = _assumptions(original, context, constraints)
        ready = bool(original) and not missing
        confidence = 0.72 if ready else max(0.2, 0.58 - (0.08 * len(missing)))

        result = ClarifiedProblem(
            id=_new_id("clarified_problem"),
            original_problem=original,
            normalized_problem=normalized,
            status="ready_for_retrieval" if ready else "needs_clarification",
            clarifying_questions=questions,
            missing_information=missing,
            assumptions=assumptions,
            ready_for_retrieval=ready,
            confidence=round(confidence, 2),
        )
        return result.to_dict()

    def capture(self, payload: Mapping[str, Any] | str) -> dict[str, Any]:
        data = _coerce_payload(payload, default_key="text")
        text = _clean_text(data.get("text") or data.get("selected_text") or data.get("content") or "")
        source_data = data.get("source") if isinstance(data.get("source"), Mapping) else {}
        source_kind = _clean_text(
            source_data.get("kind")
            if isinstance(source_data, Mapping)
            else data.get("source") or data.get("source_kind") or "unknown"
        )
        source = CaptureSource(
            kind=source_kind or "unknown",
            title=_clean_text(data.get("title") or source_data.get("title") if isinstance(source_data, Mapping) else data.get("title") or ""),
            url=_clean_text(data.get("url") or source_data.get("url") if isinstance(source_data, Mapping) else data.get("url") or ""),
            content_type=_clean_text(data.get("content_type") or source_data.get("content_type") if isinstance(source_data, Mapping) else data.get("content_type") or "text/plain"),
        )

        trust_level = "untrusted" if _is_external(source) else "trusted"
        metadata = data.get("metadata") if isinstance(data.get("metadata"), Mapping) else {}
        record = CapturedInput(
            id=_new_id("captured_input"),
            text=text,
            source=source,
            trust_level=trust_level,
            status="pending_input",
            write_policy="pending_review_only",
            captured_at=_now(),
            metadata={
                **dict(metadata),
                "adapter": "prompt-orchestrator",
                "phase": "5",
                "input_only": True,
            },
        )
        item = record.to_dict()
        if self.persist_inputs:
            self._append_pending_input(item)
        return item

    def knowledge_summary(self, payload: Mapping[str, Any] | None = None) -> dict[str, Any]:
        data = payload or {}
        sources = _listify_records(data.get("sources"))
        claims = _listify_records(data.get("claims"))
        pending_inputs = _listify_records(data.get("pending_inputs"))

        if not pending_inputs:
            pending_inputs = self._read_pending_inputs()

        warnings: list[str] = []
        adapter_mode = "caller_supplied" if sources or claims else "mock_safe_empty"
        if not sources and not claims:
            warnings.append("No formal Knowledge OS sources or claims were supplied to the prompt adapter.")
        if pending_inputs:
            warnings.append("Pending inputs are not formal knowledge and require review before promotion.")

        summary = (
            f"Knowledge OS summary: {len(sources)} sources, {len(claims)} claims, "
            f"{len(pending_inputs)} pending inputs."
        )
        result = KnowledgeOSSummary(
            adapter_mode=adapter_mode,
            sources_count=len(sources),
            claims_count=len(claims),
            pending_inputs_count=len(pending_inputs),
            review_required_count=len(pending_inputs),
            summary=summary,
            warnings=warnings,
        )
        return result.to_dict()

    def _append_pending_input(self, item: Mapping[str, Any]) -> None:
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        with self.pending_inputs_path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(item, ensure_ascii=True, sort_keys=True) + "\n")

    def _read_pending_inputs(self) -> list[dict[str, Any]]:
        if not self.pending_inputs_path.exists():
            return []
        items: list[dict[str, Any]] = []
        for line in self.pending_inputs_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                parsed = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                items.append(parsed)
        return items


def _coerce_payload(payload: Mapping[str, Any] | str, *, default_key: str) -> dict[str, Any]:
    if isinstance(payload, str):
        return {default_key: payload}
    return dict(payload)


def _clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _listify(value: Any) -> list[str]:
    if value is None or value == "":
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [_clean_text(item) for item in value if _clean_text(item)]
    return [_clean_text(value)]


def _listify_records(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, Mapping)]


def _normalize_problem(problem: str, goal: str) -> str:
    if not problem:
        return ""
    if goal:
        return f"{problem} Goal: {goal}"
    return problem


def _missing_information(
    problem: str,
    context: str,
    goal: str,
    constraints: list[str],
) -> list[str]:
    missing: list[str] = []
    if not problem:
        return ["problem_statement", "desired_outcome", "decision_context"]
    if len(problem) < 24:
        missing.append("specific_problem_detail")
    if not goal and not _has_decision_signal(problem):
        missing.append("desired_outcome")
    if not context and len(problem) < 120:
        missing.append("decision_context")
    if not constraints:
        missing.append("constraints_or_success_criteria")
    return missing[:5]


def _clarifying_questions(missing: list[str]) -> list[str]:
    question_map = {
        "problem_statement": "What exact problem or decision should be handled?",
        "specific_problem_detail": "What concrete situation, product, user, or workflow is this about?",
        "desired_outcome": "What output or decision would make this successful?",
        "decision_context": "What background facts, evidence, or constraints should be considered first?",
        "constraints_or_success_criteria": "What constraints, risks, or acceptance criteria must the answer respect?",
    }
    return [question_map[item] for item in missing if item in question_map]


def _assumptions(problem: str, context: str, constraints: list[str]) -> list[str]:
    assumptions: list[str] = []
    if problem:
        assumptions.append("Treat the user input as a draft problem statement, not verified fact.")
    if context:
        assumptions.append("Use supplied context only as unverified working context until retrieval confirms it.")
    if constraints:
        assumptions.append("Respect caller-supplied constraints before generating downstream prompts.")
    if not assumptions:
        assumptions.append("No domain facts are assumed.")
    return assumptions


def _has_decision_signal(problem: str) -> bool:
    lowered = problem.lower()
    signals = ["decide", "decision", "choose", "should", "whether", "compare", "plan", "recommend"]
    return any(signal in lowered for signal in signals)


def _is_external(source: CaptureSource) -> bool:
    if source.kind.lower() in EXTERNAL_SOURCE_KINDS:
        return True
    return bool(source.url or source.kind.lower().startswith("http"))


def _new_id(prefix: str) -> str:
    return f"{prefix}_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
