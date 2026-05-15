from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from app.agent.tool_schema import BaseTool, ToolResult
from app.core.config import settings
from app.core.errors import AppError


class AnalyzeCSVArgs(BaseModel):
    path: str = Field(min_length=1)


class AnalyzeCSVTool(BaseTool):
    name = "analyze_csv"
    description = "Analyze a CSV file under data/raw and return simple numeric summaries."
    args_schema = AnalyzeCSVArgs

    def __init__(self, project_root: Path | None = None) -> None:
        self.project_root = (project_root or settings.project_root).resolve()
        self.allowed_root = self.project_root / "data" / "raw"

    def run(self, args: AnalyzeCSVArgs, trace_id: str) -> ToolResult:
        path = self._resolve_path(args.path)
        try:
            import pandas as pd
        except ImportError as exc:
            raise AppError("pandas is required to analyze CSV files", status_code=500, code="missing_dependency") from exc

        frame = pd.read_csv(path)
        numeric = frame.select_dtypes(include="number")
        mean = {column: float(value) for column, value in numeric.mean().to_dict().items()}
        minimum = {column: float(value) for column, value in numeric.min().to_dict().items()}
        maximum = {column: float(value) for column, value in numeric.max().to_dict().items()}
        return ToolResult(
            success=True,
            tool_name=self.name,
            output={
                "columns": [str(column) for column in frame.columns],
                "row_count": int(len(frame)),
                "numeric_summary": {"mean": mean, "min": minimum, "max": maximum},
                "mean": mean,
                "min": minimum,
                "max": maximum,
            },
        )

    def _resolve_path(self, raw_path: str) -> Path:
        path = Path(raw_path)
        if not path.is_absolute():
            path = self.allowed_root / path
            if not path.exists():
                matches = sorted(self.allowed_root.glob(f"*/{raw_path}"))
                if len(matches) == 1:
                    path = matches[0]
        resolved = path.resolve()
        if resolved.suffix.lower() != ".csv":
            raise AppError("Only CSV files are allowed", status_code=400, code="invalid_csv_path")
        if not self._is_relative_to(resolved, self.allowed_root.resolve()):
            raise AppError("CSV analysis can only access data/raw", status_code=400, code="unauthorized_path")
        if not resolved.exists():
            raise AppError(f"CSV file not found: {raw_path}", status_code=404, code="csv_not_found")
        return resolved

    @staticmethod
    def _is_relative_to(path: Path, parent: Path) -> bool:
        try:
            path.relative_to(parent)
            return True
        except ValueError:
            return False
