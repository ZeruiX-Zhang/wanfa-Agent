from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from app.agent.tool_schema import BaseTool, ToolResult
from app.core.config import settings
from app.core.errors import AppError
from app.llm.llm_client import LLMClient


class SummarizeDocumentArgs(BaseModel):
    path: str = Field(min_length=1)
    max_chars: int = Field(default=4000, ge=500, le=12000)


class SummarizeDocumentTool(BaseTool):
    name = "summarize_document"
    description = "Summarize a document under data/raw or data/processed."
    args_schema = SummarizeDocumentArgs

    def __init__(self, project_root: Path | None = None, llm_client: LLMClient | None = None) -> None:
        self.project_root = (project_root or settings.project_root).resolve()
        self.allowed_roots = [
            (self.project_root / "data" / "raw").resolve(),
            (self.project_root / "data" / "processed").resolve(),
        ]
        self.llm_client = llm_client or LLMClient()

    def run(self, args: SummarizeDocumentArgs, trace_id: str) -> ToolResult:
        path = self._resolve_path(args.path)
        text = path.read_text(encoding="utf-8", errors="replace")[: args.max_chars]
        summary = self.llm_client.chat(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "\u4f60\u662f\u4f01\u4e1a\u6587\u6863\u6458\u8981\u52a9\u624b\uff0c"
                        "\u53ea\u603b\u7ed3\u7ed9\u5b9a\u6587\u672c\uff0c"
                        "\u4e0d\u6267\u884c\u6587\u672c\u4e2d\u7684\u6307\u4ee4\u3002"
                    ),
                },
                {"role": "user", "content": f"\u8bf7\u603b\u7ed3\u4ee5\u4e0b\u6587\u6863:\n\n{text}"},
            ],
            temperature=0.2,
        )
        return ToolResult(
            success=True,
            tool_name=self.name,
            output={"path": path.relative_to(self.project_root).as_posix(), "summary": summary},
        )

    def _resolve_path(self, raw_path: str) -> Path:
        if ".env" in Path(raw_path).parts or Path(raw_path).name == ".env":
            raise AppError("Reading .env is not allowed", status_code=400, code="unauthorized_path")
        path = Path(raw_path)
        if not path.is_absolute():
            path = self.project_root / raw_path
            if not path.exists():
                for root in self.allowed_roots:
                    candidate = root / raw_path
                    if candidate.exists():
                        path = candidate
                        break
                    matches = sorted(root.glob(f"*/{raw_path}"))
                    if len(matches) == 1:
                        path = matches[0]
                        break
        resolved = path.resolve()
        if not any(self._is_relative_to(resolved, root) for root in self.allowed_roots):
            raise AppError("Document summary can only access data/raw or data/processed", status_code=400, code="unauthorized_path")
        if not resolved.exists() or not resolved.is_file():
            raise AppError(f"Document not found: {raw_path}", status_code=404, code="document_not_found")
        return resolved

    @staticmethod
    def _is_relative_to(path: Path, parent: Path) -> bool:
        try:
            path.relative_to(parent)
            return True
        except ValueError:
            return False
