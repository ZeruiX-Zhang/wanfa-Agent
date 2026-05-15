from __future__ import annotations

from dataclasses import dataclass, field

from app.schemas.agent import PendingAction, Source


@dataclass
class WorkflowOutcome:
    final_answer: str
    sources: list[Source] = field(default_factory=list)
    pending_action: PendingAction | None = None
    status: str = "completed"
    severity: str = "unknown"

