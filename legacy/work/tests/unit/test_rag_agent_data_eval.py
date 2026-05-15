from __future__ import annotations

from analyst_core.agent.pipeline import DataAnalystAgent
from analyst_core.schemas.data_agent import DataAgentQueryRequest
from analyst_core.sql.safety import SQLSafetyChecker
from evaluation.runner import run_evaluation
from platform_common.models import AuthContext, UnifiedRunRequest
from platform_common.settings import ROOT_DIR, get_settings
from platform_common.traces import UnifiedTraceStore
from rag_core.rag.ingestion import chunk_text
from rag_core.rag.service import RequestContext, rag_service
from scripts.init_platform import initialize_platform
from tool_registry import get_default_registry
from workflow_core.qa.planner import QAPlanner
from workflow_core.unified_service import run_unified_agent


def test_rag_chunking_heading_aware():
    chunks = chunk_text("# A\none two\n\n# B\nthree four", strategy="heading-aware", chunk_size=40)
    assert len(chunks) >= 2
    assert chunks[0][0] == "A"


def test_rag_query_returns_citations():
    initialize_platform(reset_traces=False)
    settings = get_settings()
    result = rag_service.query("What is the enterprise customer P1 response time?", context=RequestContext(tenant_id=settings.default_tenant_id, roles=settings.default_roles))
    assert result["citations"]
    assert result["evidence_score"] >= 0


def test_tool_registry_schema_validation():
    registry = get_default_registry()
    parsed = registry.validate_args("simple_python_math", {"expression": "1 + 2 * 3"})
    assert parsed.expression
    result = registry.execute("simple_python_math", {"expression": "1 + 2 * 3"})
    assert result["result"] == 7
    pending = registry.execute("create_ticket_mock", {"title": "x", "description": "y"})
    assert pending["status"] == "pending_confirmation"


def test_agent_max_steps_guard():
    path = ROOT_DIR / "storage" / "traces" / "test_max_steps_runs.jsonl"
    if path.exists():
        path.unlink()
    store = UnifiedTraceStore(path=path)
    response = run_unified_agent(
        UnifiedRunRequest(user_input="Summarize the 2025 quarterly revenue trend and cite supporting sources.", mode="hybrid", max_steps=1),
        AuthContext(user_id="u", tenant_id="demo", roles=["employee", "finance", "analyst"]),
        trace_store=store,
    )
    assert response.status == "error"
    assert "max_steps" in response.final_answer


def test_qa_planner_multihop_and_data_default_disabled():
    analysis, plan = QAPlanner().build(
        "Compare the P1 customer response time and when rollback approval is required.",
        scenario="unknown",
        intent="knowledge_question",
        mode="auto",
    )
    assert analysis.is_multi_hop
    assert len(plan.steps) >= 2
    assert plan.allow_data_tool is False

    data_analysis, data_plan = QAPlanner().build(
        "Use the local data table to build a chart.",
        scenario="unknown",
        intent="unknown",
        mode="auto",
    )
    assert data_analysis.needs_clarification
    assert data_analysis.requires_data_tool is False
    assert data_plan.steps == []


def test_unified_agent_returns_qa_audit_artifacts():
    initialize_platform(reset_traces=False)
    path = ROOT_DIR / "storage" / "traces" / "test_qa_runs.jsonl"
    if path.exists():
        path.unlink()
    response = run_unified_agent(
        UnifiedRunRequest(
            user_input="Compare the P1 customer response time and when rollback approval is required.",
            mode="auto",
            max_steps=8,
        ),
        AuthContext(user_id="u", tenant_id="demo", roles=["employee", "support", "ops", "analyst"]),
        trace_store=UnifiedTraceStore(path=path),
    )
    assert response.status == "completed"
    assert response.answer_type in {"direct_answer", "insufficient_evidence"}
    assert response.qa_plan["steps"]
    assert "subquestions" in response.evidence_report
    assert response.verification["status"] in {"passed", "insufficient"}
    assert "run_structured_analysis" not in [step.name for step in response.tool_steps]


def test_restricted_chunks_do_not_enter_agent_sources():
    initialize_platform(reset_traces=False)
    response = run_unified_agent(
        UnifiedRunRequest(
            user_input="What does the executive-only acquisition planning document say?",
            mode="auto",
            max_steps=8,
        ),
        AuthContext(user_id="u", tenant_id="demo", roles=["employee", "support", "ops", "analyst"]),
        trace_store=UnifiedTraceStore(path=ROOT_DIR / "storage" / "traces" / "test_restricted_runs.jsonl"),
    )
    filenames = " ".join(source.title for source in response.sources)
    assert "restricted_executive_policy" not in filenames


def test_sql_safety_checker_blocks_dangerous_sql():
    checker = SQLSafetyChecker(max_result_rows=10)
    assert checker.validate("SELECT * FROM orders").is_valid
    assert not checker.validate("SELECT * FROM orders; DROP TABLE orders").is_valid
    assert not checker.validate("DELETE FROM orders").is_valid


def test_data_agent_query_demo_db():
    initialize_platform(reset_traces=False)
    response = DataAnalystAgent(enable_trace=False).run(DataAgentQueryRequest(question="Show the 2025 quarterly revenue trend."))
    assert response.status == "completed"
    assert response.sql
    assert response.row_count > 0


def test_eval_runner_smoke():
    initialize_platform(reset_traces=False)
    report = run_evaluation("rag")
    assert report["results"]["rag"]["total"] >= 10
