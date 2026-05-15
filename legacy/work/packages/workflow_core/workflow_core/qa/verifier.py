from __future__ import annotations

from workflow_core.qa.models import EvidenceReport, QAPlan, QuestionAnalysis, VerificationReport


class AnswerVerifier:
    def verify(self, analysis: QuestionAnalysis, plan: QAPlan, evidence: EvidenceReport) -> VerificationReport:
        if analysis.needs_clarification:
            return VerificationReport(
                status="needs_clarification",
                answer_type="clarification_needed",
                confidence=0.0,
                supported_step_count=0,
                total_step_count=len(plan.steps),
                missing_evidence=[analysis.clarification_question or "clarification required"],
                citation_coverage=0.0,
            )

        if not plan.steps:
            return VerificationReport(
                status="insufficient",
                answer_type="insufficient_evidence",
                confidence=0.0,
                total_step_count=0,
                missing_evidence=["no retrieval plan was produced"],
            )

        missing: list[str] = []
        supported = 0
        scores: list[float] = []
        for step, subquestion in zip(plan.steps, evidence.subquestions):
            if len(subquestion.items) >= step.required_evidence:
                supported += 1
                scores.extend(float(item.score or 0.0) for item in subquestion.items[:3])
            else:
                missing.append(step.question)

        citation_coverage = round(supported / max(len(plan.steps), 1), 4)
        avg_score = sum(scores) / max(len(scores), 1) if scores else 0.0
        confidence = min(0.95, max(0.0, 0.3 + citation_coverage * 0.35 + avg_score * 0.35))
        warnings = []
        if evidence.prompt_injection_count:
            warnings.append("retrieved_context_contains_prompt_injection_markers")
        if evidence.blocked_source_count:
            warnings.append("some_retrieved_context_was_blocked")
        if missing:
            return VerificationReport(
                status="insufficient",
                answer_type="insufficient_evidence",
                confidence=round(min(confidence, 0.45), 4),
                supported_step_count=supported,
                total_step_count=len(plan.steps),
                missing_evidence=missing,
                warnings=warnings,
                citation_coverage=citation_coverage,
            )
        return VerificationReport(
            status="passed",
            answer_type="direct_answer",
            confidence=round(confidence, 4),
            supported_step_count=supported,
            total_step_count=len(plan.steps),
            missing_evidence=[],
            warnings=warnings,
            citation_coverage=citation_coverage,
        )
