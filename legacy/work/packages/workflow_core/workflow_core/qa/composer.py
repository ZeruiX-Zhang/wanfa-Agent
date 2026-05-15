from __future__ import annotations

from workflow_core.qa.models import ComposedAnswer, EvidenceReport, QuestionAnalysis, VerificationReport
from workflow_core.schemas.agent import PendingAction


class ResponseComposer:
    def compose(
        self,
        *,
        analysis: QuestionAnalysis,
        evidence: EvidenceReport,
        verification: VerificationReport,
        pending_action: PendingAction | None = None,
    ) -> ComposedAnswer:
        if verification.answer_type == "clarification_needed":
            return ComposedAnswer(
                answer_type="clarification_needed",
                final_answer=analysis.clarification_question or "需要补充更多问题信息后才能继续。",
                confidence=0.0,
                next_actions=["补充业务域、对象、时间范围或允许的数据工具模式。"],
            )

        if verification.answer_type == "insufficient_evidence":
            missing = "；".join(verification.missing_evidence) or analysis.original_question
            return ComposedAnswer(
                answer_type="insufficient_evidence",
                final_answer=(
                    "当前知识库没有足够依据回答该问题。"
                    f"已检索 {verification.total_step_count} 个子问题，"
                    f"找到 {evidence.usable_evidence_count} 条可用证据；缺口：{missing}。"
                ),
                confidence=verification.confidence,
                limitations=["证据不足时不会强行生成结论。"],
                next_actions=["补充相关文档或放宽业务域后重新检索。"],
            )

        answer_type = "approval_required" if pending_action else "direct_answer"
        body = self._answer_body(evidence)
        citation_line = self._citation_line(evidence)
        warnings = ""
        if verification.warnings:
            warnings = "\n注意：" + "；".join(verification.warnings)
        approval = ""
        if pending_action:
            approval = f"\n该请求还包含高风险写操作 `{pending_action.tool}`，需要人工审批后才会执行。"
        return ComposedAnswer(
            answer_type=answer_type,
            final_answer=(
                f"结论：{body}\n"
                f"引用：{citation_line}\n"
                f"置信度：{verification.confidence:.2f}。"
                f"{warnings}{approval}"
            ),
            confidence=verification.confidence,
            limitations=verification.warnings,
            next_actions=["查看 trace 中的 qa_plan、evidence_report 和 verification 以审计证据路径。"],
        )

    def _answer_body(self, evidence: EvidenceReport) -> str:
        lines: list[str] = []
        for subquestion in evidence.subquestions:
            answer = subquestion.answer.strip()
            if answer:
                lines.append(answer)
            elif subquestion.items:
                snippets = " ".join((item.snippet or "")[:220] for item in subquestion.items[:2])
                lines.append(snippets)
        if not lines:
            return "当前可用证据为空。"
        deduped: list[str] = []
        for line in lines:
            if line not in deduped:
                deduped.append(line)
        return " ".join(deduped)[:1200]

    def _citation_line(self, evidence: EvidenceReport) -> str:
        labels: list[str] = []
        seen: set[str] = set()
        for subquestion in evidence.subquestions:
            for item in subquestion.items:
                key = item.chunk_id or item.document_id or item.title
                if key in seen:
                    continue
                seen.add(key)
                label = item.title or item.document_id or item.chunk_id or "source"
                labels.append(label)
                if len(labels) >= 5:
                    break
            if len(labels) >= 5:
                break
        return "，".join(labels) if labels else "无"
