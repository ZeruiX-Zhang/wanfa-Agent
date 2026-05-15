from __future__ import annotations

import re
from typing import Any

from platform_common.models import GuardrailDecision
from security import mask_pii


SECRET_PATTERNS = (
    r"(?i)\bapi[_-]?key\b",
    r"(?i)\btoken\b",
    r"(?i)\bpassword\b",
    r"(?i)\bsecret\b",
)

UNSAFE_REQUEST_PATTERNS = (
    (r"(?i)\.env", "sensitive_file_access"),
    (r"(?i)\b(delete|remove|erase|rm)\b", "destructive_intent"),
    (r"(?i)\b(shell|powershell|cmd)\b", "shell_execution_request"),
    (r"(?i)(api[_ -]?key|token|password|secret).*(send|show|print|reveal)", "secret_exfiltration"),
)

BLOCKED_TOOLS = {"run_shell", "shell", "exec", "execute_shell"}

PROMPT_INJECTION_PATTERNS = (
    (r"(?i)ignore (all )?(previous|prior) instructions", "ignore_previous_instructions"),
    (r"(?i)\bsystem prompt\b", "system_prompt_reference"),
    (r"(?i)\bdeveloper message\b", "developer_message_reference"),
    (r"(?i)\bexecute (shell|command|powershell|cmd)\b", "tool_execution_instruction"),
    (r"(?i)\breveal\b.*\b(api[_ -]?key|token|password|secret)\b", "secret_exfiltration_instruction"),
)


class GuardrailViolation(PermissionError):
    def __init__(self, decision: GuardrailDecision) -> None:
        self.decision = decision
        super().__init__(decision.reason)


class GuardrailService:
    def check_request(self, text: str) -> GuardrailDecision:
        lowered = text.strip()
        for pattern, policy_id in UNSAFE_REQUEST_PATTERNS:
            if re.search(pattern, lowered):
                return GuardrailDecision(
                    stage="request_precheck",
                    decision="block",
                    reason=f"Blocked by {policy_id}",
                    policy_ids=[policy_id],
                )
        return GuardrailDecision(
            stage="request_precheck",
            decision="allow",
            reason="request accepted",
            policy_ids=["request_allow"],
        )

    def check_tool_call(self, tool_name: str, args: dict[str, Any]) -> GuardrailDecision:
        if tool_name in BLOCKED_TOOLS:
            return GuardrailDecision(
                stage="tool_precheck",
                decision="block",
                reason=f"Tool {tool_name} is not allowed",
                policy_ids=["blocked_tool"],
            )
        serialized = str(args)
        if ".env" in serialized:
            return GuardrailDecision(
                stage="tool_precheck",
                decision="block",
                reason="Sensitive path access blocked",
                policy_ids=["sensitive_path"],
            )
        return GuardrailDecision(
            stage="tool_precheck",
            decision="allow",
            reason="tool call accepted",
            policy_ids=["tool_allow"],
        )

    def check_retrieval_context(self, source: dict[str, Any]) -> GuardrailDecision:
        text = " ".join(str(source.get(key) or "") for key in ("title", "snippet", "text", "document_id", "chunk_id"))
        policy_ids: list[str] = []
        for pattern, policy_id in PROMPT_INJECTION_PATTERNS:
            if re.search(pattern, text):
                policy_ids.append(policy_id)
        if ".env" in text and re.search(r"(?i)(read|show|print|reveal|send)", text):
            return GuardrailDecision(
                stage="retrieval_precheck",
                decision="block",
                reason="Retrieved context appears to request sensitive file disclosure.",
                policy_ids=["retrieval_sensitive_file"],
            )
        if policy_ids:
            return GuardrailDecision(
                stage="retrieval_precheck",
                decision="review",
                reason="Retrieved chunk contains prompt-injection style instructions; treat as untrusted evidence.",
                policy_ids=policy_ids,
            )
        return GuardrailDecision(
            stage="retrieval_precheck",
            decision="allow",
            reason="retrieved context accepted",
            policy_ids=["retrieval_allow"],
        )

    def check_output(self, text: str) -> tuple[GuardrailDecision, str]:
        redactions: list[str] = []
        sanitized = mask_pii(text)
        for pattern in SECRET_PATTERNS:
            if re.search(pattern, sanitized):
                sanitized = re.sub(pattern, "***REDACTED***", sanitized)
                redactions.append(pattern)
        decision = GuardrailDecision(
            stage="output_postcheck",
            decision="review" if redactions else "allow",
            reason="output redacted" if redactions else "output accepted",
            policy_ids=["output_redaction"] if redactions else ["output_allow"],
            redactions=redactions,
        )
        return decision, sanitized
