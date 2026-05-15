from __future__ import annotations

from analyst_core.service import AnalysisServiceResult, run_analysis


def run_structured_analysis(question: str) -> AnalysisServiceResult:
    return run_analysis(question, include_trace=False, enable_internal_trace=False)
