from __future__ import annotations

import json

from app.agent.agent_runner import AgentRunner
from app.agent.tool_registry import ToolRegistry
from app.agent.tool_schema import BaseTool, ToolResult
from app.agent.trace_store import TraceStore
from app.tools.analyze_csv import AnalyzeCSVTool
from app.tools.calculate import CalculateTool
from app.tools.summarize_document import SummarizeDocumentTool


class FakeLLMClient:
    def chat(self, messages: list[dict[str, str]], temperature: float = 0.2) -> str:
        return "\u6458\u8981\u7ed3\u679c"


class FakeTool(BaseTool):
    name = "analyze_csv"
    description = "fake analyze csv"
    args_schema = AnalyzeCSVTool.args_schema

    def run(self, args, trace_id: str) -> ToolResult:
        return ToolResult(success=True, tool_name=self.name, output={"row_count": 2, "mean": {"revenue": 150.0}})


def test_calculate_rejects_unsafe_expression():
    tool = CalculateTool()

    result = tool.run(CalculateTool.args_schema(expression="1 + 2 * 3"), trace_id="trace")
    assert result.output["result"] == 7.0

    registry = ToolRegistry([tool])
    denied = registry.execute("calculate", {"expression": "__import__('os').system('dir')"}, trace_id="trace")
    assert denied.success is False
    assert "unsupported" in denied.error or "unsafe" in denied.error


def test_analyze_csv_limited_to_data_raw(tmp_path):
    raw_dir = tmp_path / "data" / "raw"
    raw_dir.mkdir(parents=True)
    (raw_dir / "sales_report.csv").write_text("month,revenue\n2026-01,100\n2026-02,200\n", encoding="utf-8")

    tool = AnalyzeCSVTool(project_root=tmp_path)
    result = tool.run(AnalyzeCSVTool.args_schema(path="sales_report.csv"), trace_id="trace")

    assert result.success is True
    assert result.output["row_count"] == 2
    assert result.output["mean"]["revenue"] == 150.0

    denied = ToolRegistry([tool]).execute("analyze_csv", {"path": "../.env"}, trace_id="trace")
    assert denied.success is False


def test_summarize_document_rejects_env(tmp_path):
    raw_dir = tmp_path / "data" / "raw"
    raw_dir.mkdir(parents=True)
    (raw_dir / "policy.md").write_text("\u62a5\u9500\u5236\u5ea6", encoding="utf-8")
    (tmp_path / ".env").write_text("OPENAI_API_KEY=secret", encoding="utf-8")

    tool = SummarizeDocumentTool(project_root=tmp_path, llm_client=FakeLLMClient())
    result = tool.run(SummarizeDocumentTool.args_schema(path="policy.md"), trace_id="trace")
    denied = ToolRegistry([tool]).execute("summarize_document", {"path": ".env"}, trace_id="trace")

    assert result.success is True
    assert result.output["summary"] == "\u6458\u8981\u7ed3\u679c"
    assert denied.success is False


def test_agent_runner_creates_trace(tmp_path):
    registry = ToolRegistry([FakeTool()])
    trace_store = TraceStore(storage_dir=tmp_path / "storage" / "traces")
    runner = AgentRunner(tool_registry=registry, trace_store=trace_store, llm_client=FakeLLMClient())

    response = runner.run(
        "\u5206\u6790 sales_report.csv \u7684\u6536\u5165\u5747\u503c\u3001"
        "\u6700\u5927\u503c\u3001\u6700\u5c0f\u503c",
        max_steps=4,
        trace_id="trace",
    )
    trace_path = tmp_path / "storage" / "traces" / f"{response.run_id}.json"
    trace = json.loads(trace_path.read_text(encoding="utf-8"))

    assert response.success is True
    assert response.tools_used == ["analyze_csv"]
    assert trace["run_id"] == response.run_id
    assert trace["steps"][0]["selected_tool"] == "analyze_csv"
