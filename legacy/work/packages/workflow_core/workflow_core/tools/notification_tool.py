from __future__ import annotations

from typing import Any

from workflow_core.schemas.agent import Ticket
from workflow_core.tools.ticket_tool import create_ticket


def notify_human_agent(
    target_role: str,
    message: str,
    scenario: str,
    severity: str = "unknown",
    metadata: dict[str, Any] | None = None,
) -> Ticket:
    return create_ticket(
        title=f"閫氱煡{target_role}",
        description=message,
        scenario=scenario,
        severity=severity,
        ticket_type="notification",
        metadata={"target_role": target_role, **(metadata or {})},
    )


