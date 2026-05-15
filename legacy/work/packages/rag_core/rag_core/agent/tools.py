from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from rag_core.core.config import AGENT_CORE_ROOT
from rag_core.rag.service import RequestContext, rag_service
from rag_core.security.output_sanitizer import sanitize_output
from rag_core.security.path_guard import PathGuardError, ensure_within_allowed_path


class KnowledgeSearchArgs(BaseModel):
    query: str = Field(min_length=1)
    domain: str | None = None
    top_k: int = Field(default=3, ge=1, le=10)


class ReadAllowedFileArgs(BaseModel):
    path: str = Field(min_length=1)


class AnalyzeCsvArgs(BaseModel):
    path: str = Field(default="data/raw/data_analysis/sales_report.csv", min_length=1)
    column: str = Field(default="revenue", min_length=1)


class ToolRegistry:
    allowed_tools = {"search_knowledge", "search_knowledge_base", "read_allowed_file", "analyze_csv"}

    def run(self, name: str, args: dict[str, Any], context: RequestContext) -> dict[str, Any]:
        if name not in self.allowed_tools:
            raise ValueError("tool is not allowed")
        if name in {"search_knowledge", "search_knowledge_base"}:
            parsed = KnowledgeSearchArgs.model_validate(args)
            result = rag_service.query(parsed.query, top_k=parsed.top_k, domain=parsed.domain, context=context)
            return {"answer": sanitize_output(str(result["answer"])), "sources": result["sources"]}
        if name == "read_allowed_file":
            parsed = ReadAllowedFileArgs.model_validate(args)
            path = ensure_within_allowed_path(parsed.path, [AGENT_CORE_ROOT])
            if path.name == ".env" or ".env" in path.parts:
                raise PathGuardError("agent tools may not read .env files")
            if not path.is_file():
                raise FileNotFoundError(path)
            return {"content": sanitize_output(path.read_text(encoding="utf-8")[:4000])}
        if name == "analyze_csv":
            parsed = AnalyzeCsvArgs.model_validate(args)
            return _analyze_csv(parsed.path, parsed.column)
        raise ValueError("tool is not implemented")


tool_registry = ToolRegistry()


def _analyze_csv(path: str, column: str) -> dict[str, Any]:
    csv_root = (AGENT_CORE_ROOT / "data" / "raw" / "data_analysis").resolve()
    requested = Path(path)
    resolved = requested if requested.is_absolute() else AGENT_CORE_ROOT / requested
    csv_path = ensure_within_allowed_path(resolved, [csv_root])
    if csv_path.suffix.lower() != ".csv":
        raise PathGuardError("analyze_csv only accepts CSV files")
    if not csv_path.is_file():
        raise FileNotFoundError(csv_path)

    with csv_path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        rows = list(reader)
        columns = list(reader.fieldnames or [])

    if column not in columns and column == "收入" and "revenue" in columns:
        column = "revenue"
    if column not in columns:
        raise ValueError(f"CSV column not found: {column}")

    values: list[float] = []
    for row in rows:
        raw_value = str(row.get(column, "")).strip().replace(",", "")
        if raw_value:
            values.append(float(raw_value))
    if not values:
        raise ValueError(f"CSV column has no numeric values: {column}")

    mean_value = sum(values) / len(values)
    min_value = min(values)
    max_value = max(values)
    metrics = {
        "column": column,
        "mean": mean_value,
        "max": max_value,
        "min": min_value,
    }
    answer = (
        f"{csv_path.name} includes columns {', '.join(columns)} across {len(rows)} rows; "
        f"{column} mean={mean_value:g}, max={max_value:g}, min={min_value:g}."
    )
    return {
        "answer": sanitize_output(answer),
        "filename": csv_path.name,
        "column_names": columns,
        "row_count": len(rows),
        "metrics": metrics,
    }
