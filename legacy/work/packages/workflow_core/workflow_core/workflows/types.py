from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from workflow_core.schemas.agent import PendingAction, Source


@dataclass
class WorkflowOutcome:
    final_answer: str
    sources: list[Source] = field(default_factory=list)
    pending_action: PendingAction | None = None
    status: str = "completed"
    severity: str = "unknown"
    mode: str = "auto"
    data_artifacts: list[dict[str, Any]] = field(default_factory=list)
    answer_type: str | None = None
    confidence: float | None = None
    qa_plan: dict[str, Any] = field(default_factory=dict)
    evidence_report: dict[str, Any] = field(default_factory=dict)
    verification: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
