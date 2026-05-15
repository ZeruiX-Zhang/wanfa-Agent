from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.core.errors import AppError


SUPPORTED_EXTENSIONS = {".md", ".txt", ".pdf", ".csv"}


@dataclass(frozen=True)
class LoadedDocument:
    text: str
    metadata: dict[str, Any]


class DocumentLoader:
    def __init__(self, project_root: Path | None = None) -> None:
        self.project_root = (project_root or settings.project_root).resolve()

    def load_directory(self, directory: str, glob_pattern: str = "**/*") -> list[LoadedDocument]:
        root = self._resolve_safe_path(directory)
        if not root.exists() or not root.is_dir():
            raise AppError(f"Directory not found: {directory}", status_code=404, code="directory_not_found")

        documents: list[LoadedDocument] = []
        for path in sorted(root.glob(glob_pattern)):
            if not path.is_file():
                continue
            if path.name == ".env":
                continue
            if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
                continue
            documents.extend(self.load_file(path))
        return documents

    def load_file(self, path: Path) -> list[LoadedDocument]:
        path = self._resolve_safe_path(str(path))
        suffix = path.suffix.lower()
        if suffix in {".md", ".txt"}:
            return [self._load_text(path)]
        if suffix == ".pdf":
            return self._load_pdf(path)
        if suffix == ".csv":
            return [self._load_csv(path)]
        raise AppError(f"Unsupported file type: {suffix}", status_code=400, code="unsupported_file_type")

    def _load_text(self, path: Path) -> LoadedDocument:
        return LoadedDocument(text=path.read_text(encoding="utf-8", errors="replace"), metadata=self._base_metadata(path))

    def _load_pdf(self, path: Path) -> list[LoadedDocument]:
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise AppError("pypdf is required to read PDF files", status_code=500, code="missing_dependency") from exc

        reader = PdfReader(str(path))
        documents: list[LoadedDocument] = []
        for page_index, page in enumerate(reader.pages, start=1):
            metadata = self._base_metadata(path)
            metadata["page"] = page_index
            documents.append(LoadedDocument(text=page.extract_text() or "", metadata=metadata))
        return documents

    def _load_csv(self, path: Path) -> LoadedDocument:
        try:
            import pandas as pd
        except ImportError as exc:
            raise AppError("pandas is required to read CSV files", status_code=500, code="missing_dependency") from exc

        frame = pd.read_csv(path)
        text = "Columns: " + ", ".join(str(column) for column in frame.columns) + "\n"
        text += frame.to_csv(index=False)
        return LoadedDocument(text=text, metadata=self._base_metadata(path))

    def _base_metadata(self, path: Path) -> dict[str, Any]:
        relative_path = path.resolve().relative_to(self.project_root).as_posix()
        return {
            "filename": path.name,
            "source": "local",
            "path": relative_path,
            "page": None,
            "doc_type": path.suffix.lower().lstrip(".") or "text",
            "section_path": [path.stem],
        }

    def _resolve_safe_path(self, raw_path: str) -> Path:
        path = Path(raw_path)
        resolved = path if path.is_absolute() else self.project_root / path
        resolved = resolved.resolve()
        if not self._is_relative_to(resolved, self.project_root):
            raise AppError("Path must stay inside the project directory", status_code=400, code="unsafe_path")
        return resolved

    @staticmethod
    def _is_relative_to(path: Path, parent: Path) -> bool:
        try:
            path.relative_to(parent)
            return True
        except ValueError:
            return False
