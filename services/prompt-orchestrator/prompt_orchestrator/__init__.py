"""Prompt orchestrator adapter surface for Reality OS Phase 5."""

from .adapter import (
    PromptOrchestratorAdapter,
    build_prompt_adapter,
    capture_input,
    clarify_problem,
    knowledge_os_summary,
)

__all__ = [
    "PromptOrchestratorAdapter",
    "build_prompt_adapter",
    "capture_input",
    "clarify_problem",
    "knowledge_os_summary",
]
