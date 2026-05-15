from __future__ import annotations

import json
from pathlib import Path

from app.core.config import settings
from app.core.errors import AppError
from app.rag.rag_service import RAGService
from app.schemas.domain import DomainRequestValue, SUPPORTED_DOMAINS
from app.schemas.eval import EvalItemResult, EvalRunResponse


class EvalService:
    def __init__(self, project_root: Path | None = None, rag_service: RAGService | None = None) -> None:
        self.project_root = (project_root or settings.project_root).resolve()
        self.rag_service = rag_service or RAGService()

    def run(self, eval_file: str, domain: DomainRequestValue, top_k: int, trace_id: str) -> EvalRunResponse:
        path = self._resolve_eval_file(eval_file)
        inferred_domain = self._infer_domain(path)
        rows = self._read_jsonl(path)
        results: list[EvalItemResult] = []
        for row in rows:
            question = str(row["question"])
            item_domain = str(row.get("domain") or domain)
            if item_domain == "auto":
                item_domain = inferred_domain
            expected_source = str(row.get("expected_source", ""))
            expected_keywords = [str(item) for item in row.get("expected_keywords", [])]
            rag_response = self.rag_service.query(
                question=question,
                domain=item_domain,  # type: ignore[arg-type]
                top_k=top_k,
                trace_id=trace_id,
            )
            source_hit = any(source.filename == expected_source for source in rag_response.sources)
            keyword_hit = any(keyword in rag_response.answer for keyword in expected_keywords)
            score = (0.5 if source_hit else 0.0) + (0.5 if keyword_hit else 0.0)
            results.append(
                EvalItemResult(
                    question=question,
                    answer=rag_response.answer,
                    sources=rag_response.sources,
                    expected_source=expected_source,
                    source_hit=source_hit,
                    keyword_hit=keyword_hit,
                    score=score,
                )
            )

        average_score = sum(result.score for result in results) / len(results) if results else 0.0
        return EvalRunResponse(
            success=True,
            total=len(results),
            results=results,
            average_score=average_score,
            trace_id=trace_id,
        )

    def _resolve_eval_file(self, eval_file: str) -> Path:
        if ".env" in Path(eval_file).parts or Path(eval_file).name == ".env":
            raise AppError("Reading .env is not allowed", status_code=400, code="unauthorized_path")
        path = Path(eval_file)
        resolved = (path if path.is_absolute() else self.project_root / path).resolve()
        if not self._is_relative_to(resolved, self.project_root):
            raise AppError("Eval file must stay inside the project directory", status_code=400, code="unsafe_path")
        if not resolved.exists() or not resolved.is_file():
            raise AppError(f"Eval file not found: {eval_file}", status_code=404, code="eval_file_not_found")
        return resolved

    def _infer_domain(self, path: Path) -> DomainRequestValue:
        stem = path.stem
        if stem.endswith("_eval"):
            candidate = stem[: -len("_eval")]
            if candidate in SUPPORTED_DOMAINS:
                return candidate  # type: ignore[return-value]
        return "auto"

    def _read_jsonl(self, path: Path) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        with path.open("r", encoding="utf-8") as file:
            for line_number, line in enumerate(file, start=1):
                if not line.strip():
                    continue
                try:
                    item = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise AppError(f"Invalid JSONL at line {line_number}", status_code=400, code="invalid_eval_jsonl") from exc
                if "question" not in item:
                    raise AppError(f"Missing question at line {line_number}", status_code=400, code="invalid_eval_item")
                rows.append(item)
        return rows

    @staticmethod
    def _is_relative_to(path: Path, parent: Path) -> bool:
        try:
            path.relative_to(parent)
            return True
        except ValueError:
            return False
