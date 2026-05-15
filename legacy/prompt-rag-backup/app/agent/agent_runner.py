from __future__ import annotations

import re
import time
from uuid import uuid4

from app.agent.tool_registry import ToolRegistry
from app.agent.trace_store import TraceStore
from app.core.errors import AppError
from app.llm.llm_client import LLMClient
from app.rag.prompts import AGENT_SYSTEM_PROMPT
from app.schemas.agent import AgentRunResponse


class AgentRunner:
    def __init__(
        self,
        tool_registry: ToolRegistry | None = None,
        trace_store: TraceStore | None = None,
        llm_client: LLMClient | None = None,
    ) -> None:
        self.tool_registry = tool_registry or ToolRegistry.default()
        self.trace_store = trace_store or TraceStore()
        self.llm_client = llm_client or LLMClient()

    def run(self, user_input: str, max_steps: int, trace_id: str) -> AgentRunResponse:
        if max_steps < 1 or max_steps > 8:
            raise AppError("max_steps must be between 1 and 8", status_code=400, code="invalid_max_steps")

        run_id = str(uuid4())
        start = time.perf_counter()
        tool_plan = self._plan_tools(user_input)[:max_steps]
        steps: list[dict[str, object]] = []
        tools_used: list[str] = []

        for step_number, (tool_name, tool_args) in enumerate(tool_plan, start=1):
            tool_start = time.perf_counter()
            result = self.tool_registry.execute(tool_name, tool_args, trace_id=trace_id)
            latency_ms = (time.perf_counter() - tool_start) * 1000
            tools_used.append(tool_name)
            steps.append(
                {
                    "step": step_number,
                    "selected_tool": tool_name,
                    "tool_args": tool_args,
                    "tool_result": result.model_dump(),
                    "latency_ms": latency_ms,
                }
            )

        final_answer = self._final_answer(user_input=user_input, steps=steps)
        latency_ms = (time.perf_counter() - start) * 1000
        trace = {
            "run_id": run_id,
            "user_input": user_input,
            "steps": steps,
            "final_answer": final_answer,
            "latency_ms": latency_ms,
            "created_at": self.trace_store.now_iso(),
        }
        self.trace_store.save(run_id, trace)
        return AgentRunResponse(
            success=True,
            run_id=run_id,
            final_answer=final_answer,
            tools_used=tools_used,
            latency_ms=latency_ms,
            trace_id=trace_id,
        )

    def _plan_tools(self, user_input: str) -> list[tuple[str, dict[str, object]]]:
        lowered = user_input.lower()
        plan: list[tuple[str, dict[str, object]]] = []

        csv_path = self._find_filename(user_input, ".csv") or "sales_report.csv"
        if any(
            keyword in lowered
            for keyword in [
                "csv",
                "\u8868\u683c",
                "\u6536\u5165",
                "\u5747\u503c",
                "\u5e73\u5747",
                "\u6700\u5927\u503c",
                "\u6700\u5c0f\u503c",
            ]
        ):
            plan.append(("analyze_csv", {"path": csv_path}))

        if any(
            keyword in lowered
            for keyword in [
                "\u8ba1\u7b97",
                "\u52a0",
                "\u51cf",
                "\u4e58",
                "\u9664",
                "\u767e\u5206\u6bd4",
            ]
        ):
            expression = self._extract_expression(user_input)
            if expression:
                plan.append(("calculate", {"expression": expression}))

        if any(keyword in lowered for keyword in ["\u603b\u7ed3", "\u6458\u8981"]):
            doc_path = (
                self._find_filename(user_input, ".md")
                or self._find_filename(user_input, ".txt")
                or self._find_filename(user_input, ".jsonl")
            )
            if doc_path:
                plan.append(("summarize_document", {"path": doc_path}))

        needs_kb = any(
            keyword in lowered
            for keyword in [
                "\u77e5\u8bc6\u5e93",
                "sla",
                "p1",
                "\u4f01\u4e1a\u5ba2\u6237",
                "\u62a5\u9500",
                "\u653f\u7b56",
            ]
        )
        if needs_kb or not plan:
            plan.append(("search_knowledge_base", {"query": user_input, "top_k": 5}))

        return plan

    def _final_answer(self, user_input: str, steps: list[dict[str, object]]) -> str:
        prompt = self._build_final_prompt(user_input, steps)
        try:
            return self.llm_client.chat(
                messages=[
                    {"role": "system", "content": AGENT_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.2,
            )
        except AppError:
            return self._fallback_final_answer(steps)

    def _build_final_prompt(self, user_input: str, steps: list[dict[str, object]]) -> str:
        return (
            f"\u7528\u6237\u4efb\u52a1:\n{user_input}\n\n"
            f"\u5de5\u5177\u6267\u884c\u8bb0\u5f55:\n{steps}\n\n"
            "\u8bf7\u57fa\u4e8e\u5de5\u5177\u7ed3\u679c\u7ed9\u51fa\u6700\u7ec8\u56de\u7b54\uff0c"
            "\u5fc5\u987b\u8bf4\u660e:\n"
            "1. \u8c03\u7528\u4e86\u54ea\u4e9b\u5de5\u5177\u3002\n"
            "2. \u6bcf\u4e2a\u5de5\u5177\u8fd4\u56de\u7684\u5173\u952e\u4fe1\u606f\u3002\n"
            "3. \u5982\u679c\u5de5\u5177\u5931\u8d25\uff0c\u5931\u8d25\u5728\u54ea\u91cc\u3002\n"
        )

    def _fallback_final_answer(self, steps: list[dict[str, object]]) -> str:
        lines = ["\u5de5\u5177\u8c03\u7528\u7ed3\u679c\u6c47\u603b:"]
        for step in steps:
            result = step["tool_result"]
            lines.append(f"- {step['selected_tool']}: {result}")
        return "\n".join(lines)

    def _find_filename(self, text: str, suffix: str) -> str | None:
        pattern = rf"[\w./\\-]+{re.escape(suffix)}"
        match = re.search(pattern, text, flags=re.IGNORECASE)
        return match.group(0) if match else None

    def _extract_expression(self, text: str) -> str | None:
        match = re.search(r"[0-9][0-9\s+\-*/().%]*", text)
        if not match:
            return None
        return match.group(0).replace("%", "/100")
