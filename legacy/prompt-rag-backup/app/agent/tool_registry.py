from __future__ import annotations

from app.agent.tool_schema import BaseTool, ToolResult
from app.core.errors import AppError
from app.tools.analyze_csv import AnalyzeCSVTool
from app.tools.calculate import CalculateTool
from app.tools.search_knowledge_base import SearchKnowledgeBaseTool
from app.tools.summarize_document import SummarizeDocumentTool


class ToolRegistry:
    def __init__(self, tools: list[BaseTool]) -> None:
        self._tools = {tool.name: tool for tool in tools}

    @classmethod
    def default(cls) -> "ToolRegistry":
        return cls(
            tools=[
                SearchKnowledgeBaseTool(),
                CalculateTool(),
                SummarizeDocumentTool(),
                AnalyzeCSVTool(),
            ]
        )

    def list_tools(self) -> list[str]:
        return sorted(self._tools)

    def get(self, name: str) -> BaseTool:
        if name not in self._tools:
            raise AppError(f"Tool is not allowed: {name}", status_code=400, code="tool_not_allowed")
        return self._tools[name]

    def execute(self, name: str, args: dict[str, object], trace_id: str) -> ToolResult:
        tool = self.get(name)
        try:
            parsed_args = tool.args_schema.model_validate(args)
            return tool.run(parsed_args, trace_id=trace_id)
        except AppError as exc:
            return ToolResult(success=False, tool_name=name, output={}, error=exc.message)
        except Exception as exc:
            return ToolResult(success=False, tool_name=name, output={}, error=str(exc))
