from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from analyst_core.agent.pipeline import DataAnalystAgent
from analyst_core.db.schema import retrieve_schema
from analyst_core.schemas.data_agent import DataAgentQueryRequest
from analyst_core.sql.safety import SQLSafetyChecker
from platform_common.settings import ROOT_DIR, get_settings
from rag_core.rag.service import RequestContext, rag_service
from workflow_core.unified_service import run_unified_agent
from platform_common.models import AuthContext, UnifiedRunRequest
from platform_common.traces import UnifiedTraceStore


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def run_evaluation(target: str = "all") -> dict[str, Any]:
    targets = ["rag", "agent", "data-agent"] if target == "all" else [target]
    report: dict[str, Any] = {"target": target, "results": {}, "failures": []}
    for item in targets:
        if item == "rag":
            report["results"]["rag"] = evaluate_rag()
        elif item == "agent":
            report["results"]["agent"] = evaluate_agent()
        elif item in {"data-agent", "data_agent", "sql"}:
            report["results"]["data-agent"] = evaluate_data_agent()
        else:
            raise ValueError(f"Unknown eval target: {item}")
    report["summary"] = _summarize(report["results"])
    return report


def evaluate_rag() -> dict[str, Any]:
    cases = load_jsonl(ROOT_DIR / "data" / "eval_sets" / "rag_eval.jsonl")
    settings = get_settings()
    context = RequestContext(tenant_id=settings.default_tenant_id, roles=settings.default_roles)
    rows: list[dict[str, Any]] = []
    for case in cases:
        question = str(case["question"])
        expected_sources = [str(item) for item in case.get("expected_sources", [])]
        result = rag_service.query(question, top_k=5, domain=case.get("domain"), context=context)
        sources = result.get("sources", [])
        rendered_sources = json.dumps(sources, ensure_ascii=False)
        expected_answer = str(case.get("expected_answer") or "")
        answer = str(result.get("answer") or "")
        source_hit = any(source in rendered_sources for source in expected_sources) if expected_sources else bool(sources)
        keyword_hit = _keyword_score(expected_answer, answer)
        rows.append(
            {
                "question": question,
                "answer_relevancy": keyword_hit,
                "faithfulness": 1.0 if sources and "No authorized context" not in answer else 0.0,
                "context_precision": 1.0 if sources else 0.0,
                "context_recall": 1.0 if source_hit else 0.0,
                "citation_accuracy": 1.0 if source_hit else 0.0,
                "passed": bool(sources) and (source_hit or keyword_hit > 0),
            }
        )
    return _aggregate(rows, ["answer_relevancy", "faithfulness", "context_precision", "context_recall", "citation_accuracy"])


def evaluate_agent() -> dict[str, Any]:
    cases = load_jsonl(ROOT_DIR / "data" / "eval_sets" / "agent_eval.jsonl")
    auth = AuthContext(user_id="eval", tenant_id="demo", roles=["employee", "support", "finance", "ops", "analyst"])
    rows: list[dict[str, Any]] = []
    store = UnifiedTraceStore(path=ROOT_DIR / "storage" / "traces" / "eval_agent_runs.jsonl")
    for case in cases:
        response = run_unified_agent(UnifiedRunRequest(user_input=case["user_task"], mode=case.get("mode", "auto"), max_steps=case.get("max_steps", 6)), auth, trace_store=store)
        actual_tools = [step.name for step in response.tool_steps]
        expected_tools = [str(tool) for tool in case.get("expected_tools", [])]
        selected = all(tool in actual_tools for tool in expected_tools)
        success_hint = str(case.get("expected_outcome") or "").lower()
        answer = response.final_answer.lower()
        expected_block = success_hint in {"blocked", "rejected"}
        rows.append(
            {
                "user_task": case["user_task"],
                "tool_selection_accuracy": 1.0 if selected else 0.0,
                "task_success": 1.0 if expected_block and response.status == "rejected" else (1.0 if not success_hint or success_hint in answer or response.status in {"completed", "waiting_approval"} else 0.0),
                "max_steps_exceeded": 1.0 if response.status == "error" and "max_steps" in answer else 0.0,
                "failure_rate": 1.0 if response.status in {"failed", "error"} else 0.0,
                "actual_tools": actual_tools,
                "passed": selected and (response.status in {"completed", "waiting_approval"} or (expected_block and response.status == "rejected")),
            }
        )
    return _aggregate(rows, ["tool_selection_accuracy", "task_success", "max_steps_exceeded", "failure_rate"])


def evaluate_data_agent() -> dict[str, Any]:
    cases = load_jsonl(ROOT_DIR / "data" / "eval_sets" / "sql_eval.jsonl")
    agent = DataAnalystAgent(enable_trace=False)
    checker = SQLSafetyChecker()
    schema = retrieve_schema()
    rows: list[dict[str, Any]] = []
    for case in cases:
        response = agent.run(DataAgentQueryRequest(question=case["question"], include_trace=False))
        sql = response.sql or ""
        safety = checker.validate(sql) if sql else response.sql_validation
        pattern = str(case.get("expected_sql_pattern") or "")
        pattern_hit = bool(re.search(pattern, sql, flags=re.IGNORECASE | re.DOTALL)) if pattern else bool(sql)
        result_hint = str(case.get("expected_result_hint") or "").lower()
        result_text = json.dumps(response.table_rows, ensure_ascii=False).lower() + " " + response.final_answer.lower()
        rows.append(
            {
                "question": case["question"],
                "sql_validity": 1.0 if pattern_hit and response.sql_plan else 0.0,
                "sql_safety_pass": 1.0 if safety.is_valid else 0.0,
                "execution_success": 1.0 if response.status == "completed" else 0.0,
                "answer_correctness_heuristic": 1.0 if not result_hint or result_hint in result_text or response.row_count > 0 else 0.0,
                "generated_sql": sql,
                "schema_tables": [table.name for table in schema.tables],
                "passed": response.status == "completed" and safety.is_valid and pattern_hit,
            }
        )
    return _aggregate(rows, ["sql_validity", "sql_safety_pass", "execution_success", "answer_correctness_heuristic"])


def write_reports(report: dict[str, Any]) -> None:
    reports_dir = ROOT_DIR / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    (reports_dir / "eval_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (reports_dir / "eval_report.md").write_text(_markdown_report(report), encoding="utf-8")


def _aggregate(rows: list[dict[str, Any]], metrics: list[str]) -> dict[str, Any]:
    summary = {metric: sum(float(row.get(metric, 0.0)) for row in rows) / max(len(rows), 1) for metric in metrics}
    failures = [row for row in rows if not row.get("passed")]
    return {"total": len(rows), "metrics": summary, "failures": failures[:10], "cases": rows}


def _summarize(results: dict[str, Any]) -> dict[str, Any]:
    return {name: {"total": result.get("total", 0), "failure_count": len(result.get("failures", [])), "metrics": result.get("metrics", {})} for name, result in results.items()}


def _keyword_score(expected: str, answer: str) -> float:
    keywords = [token for token in re.findall(r"[A-Za-z0-9_\-\u4e00-\u9fff]+", expected.lower()) if len(token) > 1]
    if not keywords:
        return 1.0 if answer else 0.0
    return sum(1 for keyword in keywords if keyword in answer.lower()) / len(keywords)


def _markdown_report(report: dict[str, Any]) -> str:
    lines = ["# Evaluation Report", "", "| Target | Total | Failures | Key Metrics |", "|---|---:|---:|---|"]
    for name, result in report.get("results", {}).items():
        metrics = ", ".join(f"{key}={value:.2f}" for key, value in result.get("metrics", {}).items())
        lines.append(f"| {name} | {result.get('total', 0)} | {len(result.get('failures', []))} | {metrics} |")
    lines.append("")
    lines.append("## Failure Samples")
    for name, result in report.get("results", {}).items():
        for failure in result.get("failures", [])[:5]:
            lines.append(f"- **{name}**: `{failure.get('question') or failure.get('user_task')}`")
    return "\n".join(lines) + "\n"
