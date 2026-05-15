from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from workflow_core.core.config import settings
from workflow_core.schemas.agent import Ticket
from workflow_core.security.policies import redact_secrets


def _store_path(path: Path | None = None) -> Path:
    actual = path or settings.ticket_path
    actual.parent.mkdir(parents=True, exist_ok=True)
    return actual


def _append_ticket(ticket: Ticket, path: Path | None = None) -> None:
    actual = _store_path(path)
    with actual.open("a", encoding="utf-8") as file:
        file.write(json.dumps(redact_secrets(ticket.model_dump()), ensure_ascii=False) + "\n")


def create_ticket(
    title: str,
    description: str,
    scenario: str,
    severity: str = "unknown",
    ticket_type: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> Ticket:
    if ticket_type is None:
        ticket_type = "incident_ticket" if scenario == "ops_runbook" else "customer_ticket"
    ticket = Ticket(
        ticket_id=f"TKT-{uuid.uuid4().hex[:10]}",
        ticket_type=ticket_type,
        title=title,
        description=description,
        severity=severity,
        scenario=scenario,
        metadata=metadata or {},
    )
    _append_ticket(ticket)
    return ticket


def list_tickets() -> list[Ticket]:
    path = _store_path()
    if not path.exists():
        return []
    tickets: list[Ticket] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            tickets.append(Ticket.model_validate(json.loads(line)))
    return tickets


def get_ticket(ticket_id: str) -> Ticket | None:
    for ticket in list_tickets():
        if ticket.ticket_id == ticket_id:
            return ticket
    return None


