"""Mock-safe verification adapter for Reality OS flows."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

from .models import (
    Claim,
    ConfidenceScore,
    Evidence,
    EvidenceBinding,
    EvidenceState,
    RagDebugTrace,
    TraceStep,
    VerificationReport,
)

RawPayload = Mapping[str, Any]

_TOKEN_RE = re.compile(r"\w+", re.UNICODE)
_STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "has",
    "have",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "to",
    "with",
}


class VerificationAdapter:
    """Deterministic adapter for evidence binding and confidence scoring.

    The adapter only projects caller-provided payloads or local mock-safe data.
    It does not call model APIs, mutate a RAG pipeline, or write knowledge.
    """

    def extract_claims(self, memo: RawPayload | str) -> tuple[Claim, ...]:
        """Extract minimal claims from a memo-like payload."""

        if isinstance(memo, str):
            text = memo.strip()
            return (Claim(id="claim-1", text=text),) if text else ()

        raw_claims = memo.get("claims", ())
        if isinstance(raw_claims, str):
            raw_claims = (raw_claims,)
        if isinstance(raw_claims, Sequence):
            claims = tuple(
                self._claim_from_raw(index=index, raw=raw)
                for index, raw in enumerate(raw_claims, start=1)
            )
            return tuple(claim for claim in claims if claim.text)

        fallback = memo.get("claim") or memo.get("decision") or memo.get("summary")
        if isinstance(fallback, str) and fallback.strip():
            return (Claim(id="claim-1", text=fallback.strip()),)
        return ()

    def collect_evidence(self, retrieval_payload: RawPayload | Sequence[RawPayload]) -> tuple[Evidence, ...]:
        """Project retrieval output into read-only evidence records."""

        if isinstance(retrieval_payload, Mapping):
            raw_items = (
                retrieval_payload.get("evidence")
                or retrieval_payload.get("results")
                or retrieval_payload.get("sources")
                or ()
            )
        else:
            raw_items = retrieval_payload

        if isinstance(raw_items, Mapping) or isinstance(raw_items, str):
            raw_items = (raw_items,)

        evidence: list[Evidence] = []
        if not isinstance(raw_items, Sequence):
            return ()

        for index, raw in enumerate(raw_items, start=1):
            projected = self._evidence_from_raw(index=index, raw=raw)
            if projected.snippet or projected.title:
                evidence.append(projected)
        return tuple(evidence)

    def project_rag_debug_trace(self, retrieval_payload: RawPayload | Sequence[RawPayload]) -> RagDebugTrace:
        """Project RAG query/debug data without changing the source pipeline."""

        if not isinstance(retrieval_payload, Mapping):
            evidence = self.collect_evidence(retrieval_payload)
            return RagDebugTrace(
                query="",
                retrieval_count=len(evidence),
                top_evidence_ids=tuple(item.id for item in evidence[:3]),
                steps=(
                    TraceStep(
                        name="adapter_projection",
                        status="mock_safe",
                        detail="Projected sequence payload into evidence records.",
                        metadata={"evidence_count": len(evidence)},
                    ),
                ),
            )

        evidence = self.collect_evidence(retrieval_payload)
        raw_trace = retrieval_payload.get("trace") or retrieval_payload.get("debug_trace") or ()
        steps = self._trace_steps_from_raw(raw_trace)
        if not steps:
            steps = (
                TraceStep(
                    name="retrieval_projection",
                    status="ok" if evidence else "empty",
                    detail="Projected retrieval payload for verification.",
                    metadata={"evidence_count": len(evidence)},
                ),
            )

        query = retrieval_payload.get("query") or retrieval_payload.get("input") or ""
        return RagDebugTrace(
            query=str(query),
            retrieval_count=len(evidence),
            top_evidence_ids=tuple(item.id for item in evidence[:3]),
            steps=steps,
        )

    def verify_claims(
        self,
        claims: Sequence[Claim],
        evidence: Sequence[Evidence],
        trace: RagDebugTrace | None = None,
    ) -> VerificationReport:
        """Bind claims to evidence and calculate confidence."""

        normalized_claims = tuple(claims)
        normalized_evidence = tuple(evidence)
        bindings: list[EvidenceBinding] = []
        confidence: list[ConfidenceScore] = []
        warnings: list[str] = []

        if not normalized_claims:
            warnings.append("No claims were available for verification.")

        for claim in normalized_claims:
            binding = self._best_binding_for_claim(claim, normalized_evidence)
            if binding is not None:
                bindings.append(binding)
                confidence.append(self._confidence_from_binding(binding))
                continue

            state = self._missing_evidence_state(claim, normalized_evidence)
            confidence.append(
                ConfidenceScore(
                    claim_id=claim.id,
                    state=state,
                    score=0.0,
                    rationale=self._missing_evidence_rationale(state),
                )
            )

        if not normalized_evidence:
            warnings.append("No evidence was provided; claims are insufficiently evidenced or unverifiable.")

        overall_state = self._overall_state(tuple(confidence))
        overall_confidence = self._overall_confidence(tuple(confidence))
        return VerificationReport(
            claims=normalized_claims,
            evidence=normalized_evidence,
            bindings=tuple(bindings),
            confidence=tuple(confidence),
            overall_state=overall_state,
            overall_confidence=overall_confidence,
            warnings=tuple(warnings),
            trace=trace,
        )

    def verify_memo(
        self,
        memo: RawPayload | str,
        retrieval_payload: RawPayload | Sequence[RawPayload],
    ) -> VerificationReport:
        """Verify memo claims against projected retrieval evidence."""

        claims = self.extract_claims(memo)
        evidence = self.collect_evidence(retrieval_payload)
        trace = self.project_rag_debug_trace(retrieval_payload)
        return self.verify_claims(claims=claims, evidence=evidence, trace=trace)

    def _claim_from_raw(self, index: int, raw: object) -> Claim:
        if isinstance(raw, Mapping):
            raw_id = raw.get("id") or raw.get("claim_id") or f"claim-{index}"
            text = raw.get("text") or raw.get("claim") or raw.get("statement") or ""
            source = raw.get("source") or "memo"
            return Claim(id=str(raw_id), text=str(text).strip(), source=str(source))
        return Claim(id=f"claim-{index}", text=str(raw).strip())

    def _evidence_from_raw(self, index: int, raw: object) -> Evidence:
        if not isinstance(raw, Mapping):
            return Evidence(id=f"evidence-{index}", title=f"Evidence {index}", snippet=str(raw).strip())

        raw_id = raw.get("id") or raw.get("evidence_id") or raw.get("source_id") or f"evidence-{index}"
        title = raw.get("title") or raw.get("name") or raw.get("source") or f"Evidence {index}"
        snippet = raw.get("snippet") or raw.get("content") or raw.get("text") or raw.get("quote") or ""
        source_uri = raw.get("source_uri") or raw.get("url") or raw.get("uri")
        source_type = raw.get("source_type") or raw.get("type") or "retrieval"
        trust = raw.get("trust") or raw.get("trust_level") or "untrusted"
        score = self._float_or_none(raw.get("score") or raw.get("similarity") or raw.get("relevance"))
        return Evidence(
            id=str(raw_id),
            title=str(title),
            snippet=str(snippet),
            source_uri=str(source_uri) if source_uri else None,
            source_type=str(source_type),
            trust=str(trust),
            score=score,
        )

    def _trace_steps_from_raw(self, raw_trace: object) -> tuple[TraceStep, ...]:
        if isinstance(raw_trace, Mapping):
            raw_trace = raw_trace.get("steps") or (raw_trace,)
        if isinstance(raw_trace, str) or not isinstance(raw_trace, Sequence):
            return ()

        steps: list[TraceStep] = []
        for index, raw in enumerate(raw_trace, start=1):
            if isinstance(raw, Mapping):
                metadata = raw.get("metadata") if isinstance(raw.get("metadata"), Mapping) else {}
                steps.append(
                    TraceStep(
                        name=str(raw.get("name") or raw.get("stage") or f"step-{index}"),
                        status=str(raw.get("status") or "ok"),
                        detail=str(raw.get("detail") or raw.get("message") or ""),
                        metadata=self._safe_metadata(metadata),
                    )
                )
            else:
                steps.append(TraceStep(name=f"step-{index}", status="ok", detail=str(raw)))
        return tuple(steps)

    def _best_binding_for_claim(
        self,
        claim: Claim,
        evidence: Sequence[Evidence],
    ) -> EvidenceBinding | None:
        claim_terms = self._tokens(claim.text)
        if not claim_terms:
            return None

        best: tuple[Evidence, float, tuple[str, ...]] | None = None
        for item in evidence:
            evidence_terms = self._tokens(f"{item.title} {item.snippet}")
            matched_terms = tuple(sorted(claim_terms.intersection(evidence_terms)))
            relevance = len(matched_terms) / max(len(claim_terms), 1)
            if best is None or relevance > best[1]:
                best = (item, relevance, matched_terms)

        if best is None:
            return None

        item, relevance, matched_terms = best
        if relevance < 0.18:
            return None

        return EvidenceBinding(
            claim_id=claim.id,
            evidence_id=item.id,
            state=EvidenceState.SUPPORTED,
            relevance=round(relevance, 3),
            rationale="Claim terms overlap with projected evidence; human review still required.",
            matched_terms=matched_terms,
        )

    def _confidence_from_binding(self, binding: EvidenceBinding) -> ConfidenceScore:
        score = min(0.95, max(0.2, binding.relevance))
        return ConfidenceScore(
            claim_id=binding.claim_id,
            state=binding.state,
            score=round(score, 3),
            rationale=f"Confidence derived from evidence relevance {binding.relevance:.3f}.",
        )

    def _missing_evidence_state(self, claim: Claim, evidence: Sequence[Evidence]) -> EvidenceState:
        if not self._tokens(claim.text):
            return EvidenceState.UNVERIFIABLE
        if not evidence:
            return EvidenceState.INSUFFICIENT_EVIDENCE
        return EvidenceState.INSUFFICIENT_EVIDENCE

    def _missing_evidence_rationale(self, state: EvidenceState) -> str:
        if state is EvidenceState.UNVERIFIABLE:
            return "Claim has no checkable terms."
        return "No evidence item met the binding threshold."

    def _overall_state(self, confidence: Sequence[ConfidenceScore]) -> EvidenceState:
        if not confidence:
            return EvidenceState.UNVERIFIABLE
        states = {score.state for score in confidence}
        if EvidenceState.CONFLICTED in states:
            return EvidenceState.CONFLICTED
        if states == {EvidenceState.SUPPORTED}:
            return EvidenceState.SUPPORTED
        if EvidenceState.SUPPORTED in states:
            return EvidenceState.INSUFFICIENT_EVIDENCE
        if states == {EvidenceState.UNVERIFIABLE}:
            return EvidenceState.UNVERIFIABLE
        return EvidenceState.INSUFFICIENT_EVIDENCE

    def _overall_confidence(self, confidence: Sequence[ConfidenceScore]) -> float:
        if not confidence:
            return 0.0
        return round(sum(score.score for score in confidence) / len(confidence), 3)

    def _tokens(self, text: str) -> set[str]:
        return {
            token.lower()
            for token in _TOKEN_RE.findall(text)
            if len(token) > 2 and token.lower() not in _STOP_WORDS
        }

    def _float_or_none(self, value: object) -> float | None:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _safe_metadata(self, metadata: Mapping[object, object]) -> dict[str, str | int | float | bool | None]:
        safe: dict[str, str | int | float | bool | None] = {}
        for key, value in metadata.items():
            if isinstance(value, (str, int, float, bool)) or value is None:
                safe[str(key)] = value
            else:
                safe[str(key)] = str(value)
        return safe
