from __future__ import annotations

from typing import Any

from guardrails.service import GuardrailService
from workflow_core.qa.composer import ResponseComposer
from workflow_core.qa.evidence import EvidenceCollector
from workflow_core.qa.models import ComposedAnswer, EvidenceReport, QAPlan, QuestionAnalysis, VerificationReport
from workflow_core.qa.planner import QAPlanner
from workflow_core.qa.verifier import AnswerVerifier
from workflow_core.schemas.agent import IntentResult, PendingAction
from workflow_core.workflows.ops_runbook import detect_severity
from workflow_core.workflows.runtime import WorkflowRuntime
from workflow_core.workflows.types import WorkflowOutcome


class QAOrchestrator:
    def __init__(
        self,
        guardrail_service: GuardrailService | None = None,
        guardrail_decisions: list[dict[str, Any]] | None = None,
    ) -> None:
        self.guardrails = guardrail_service or GuardrailService()
        self.guardrail_decisions = guardrail_decisions
        self.planner = QAPlanner()
        self.verifier = AnswerVerifier()
        self.composer = ResponseComposer()

    def run(
        self,
        *,
        user_input: str,
        scenario: str,
        intent_result: IntentResult,
        mode: str,
        runtime: WorkflowRuntime,
    ) -> WorkflowOutcome:
        plan_payload = runtime.run_tool(
            "qa_plan_question",
            {"question": user_input, "scenario": scenario, "intent": intent_result.intent, "mode": mode},
            lambda: self._build_plan_payload(user_input, scenario, intent_result.intent, mode),
        )
        analysis = QuestionAnalysis.model_validate(plan_payload["analysis"])
        plan = QAPlan.model_validate(plan_payload["plan"])

        if analysis.needs_clarification:
            evidence = EvidenceReport()
        else:
            evidence = runtime.run_tool(
                "search_knowledge_base",
                {
                    "strategy": plan.strategy,
                    "steps": len(plan.steps),
                    "domains": [step.domain for step in plan.steps],
                    "top_k": max((step.top_k for step in plan.steps), default=5),
                },
                lambda: EvidenceCollector(self.guardrails, self.guardrail_decisions).collect(plan, scenario),
            )
            evidence = EvidenceReport.model_validate(evidence)

        verification = runtime.run_tool(
            "verify_evidence",
            {
                "step_count": len(plan.steps),
                "usable_evidence_count": evidence.usable_evidence_count,
                "coverage": evidence.coverage,
            },
            lambda: self.verifier.verify(analysis, plan, evidence),
        )
        verification = VerificationReport.model_validate(verification)
        pending_action = self._pending_action(user_input, scenario, intent_result)
        composed = runtime.run_tool(
            "summarize_workflow_result",
            {
                "answer_type": verification.answer_type,
                "confidence": verification.confidence,
                "pending_action": pending_action.model_dump() if pending_action else None,
            },
            lambda: self.composer.compose(
                analysis=analysis,
                evidence=evidence,
                verification=verification,
                pending_action=pending_action,
            ),
        )
        composed = ComposedAnswer.model_validate(composed)
        sources = EvidenceCollector().to_sources(evidence)
        return WorkflowOutcome(
            final_answer=composed.final_answer,
            sources=sources,
            pending_action=pending_action,
            status="waiting_approval" if pending_action else "completed",
            severity=self._severity(user_input, scenario),
            mode="knowledge",
            answer_type=composed.answer_type,
            confidence=composed.confidence,
            qa_plan=plan.model_dump(mode="json"),
            evidence_report=evidence.model_dump(mode="json"),
            verification=verification.model_dump(mode="json"),
            metadata={
                "question_analysis": analysis.model_dump(mode="json"),
                "qa_limitations": composed.limitations,
                "qa_next_actions": composed.next_actions,
            },
        )

    def _build_plan_payload(self, user_input: str, scenario: str, intent: str, mode: str) -> dict[str, Any]:
        analysis, plan = self.planner.build(user_input, scenario, intent, mode)
        return {"analysis": analysis.model_dump(mode="json"), "plan": plan.model_dump(mode="json")}

    def _pending_action(self, user_input: str, scenario: str, intent_result: IntentResult) -> PendingAction | None:
        if scenario == "customer_support":
            if intent_result.intent in {"complaint", "create_ticket_request"}:
                return PendingAction(
                    tool="create_ticket",
                    reason="Creating a ticket is a write action and requires approval.",
                    args={
                        "title": "Customer support ticket draft",
                        "description": user_input,
                        "scenario": "customer_support",
                        "severity": "P2",
                        "ticket_type": "customer_ticket",
                        "metadata": {"intent": intent_result.intent},
                    },
                )
            if intent_result.intent == "handoff_to_human":
                return PendingAction(
                    tool="notify_human_agent",
                    reason="Human escalation is a write action and requires approval.",
                    args={
                        "target_role": "support-agent",
                        "message": user_input,
                        "scenario": "customer_support",
                        "severity": "P2",
                        "metadata": {"intent": intent_result.intent},
                    },
                )
        if scenario == "ops_runbook":
            severity = detect_severity(user_input)
            text = user_input.lower()
            needs_approval = severity in {"P0", "P1"} and (
                intent_result.intent == "incident_escalation"
                or "notify" in text
                or "on-call" in text
                or "通知" in text
                or "值班" in text
                or "升级" in text
            )
            if needs_approval and ("notify" in text or "on-call" in text or "通知" in text or "值班" in text):
                return PendingAction(
                    tool="notify_human_agent",
                    reason="Notifying on-call staff is a write action and requires approval.",
                    args={
                        "target_role": "ops-oncall",
                        "message": user_input,
                        "scenario": "ops_runbook",
                        "severity": severity,
                        "metadata": {"intent": intent_result.intent},
                    },
                )
            if needs_approval:
                return PendingAction(
                    tool="create_ticket",
                    reason="Creating an incident ticket is a write action and requires approval.",
                    args={
                        "title": f"{severity} incident draft",
                        "description": user_input,
                        "scenario": "ops_runbook",
                        "severity": severity,
                        "ticket_type": "incident_ticket",
                        "metadata": {"intent": intent_result.intent},
                    },
                )
        return None

    def _severity(self, user_input: str, scenario: str) -> str:
        return detect_severity(user_input) if scenario == "ops_runbook" else "unknown"


def run_qa_orchestrator(
    *,
    user_input: str,
    scenario: str,
    intent_result: IntentResult,
    mode: str,
    runtime: WorkflowRuntime,
    guardrail_service: GuardrailService | None = None,
    guardrail_decisions: list[dict[str, Any]] | None = None,
) -> WorkflowOutcome:
    return QAOrchestrator(guardrail_service, guardrail_decisions).run(
        user_input=user_input,
        scenario=scenario,
        intent_result=intent_result,
        mode=mode,
        runtime=runtime,
    )
