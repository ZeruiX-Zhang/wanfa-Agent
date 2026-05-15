from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class Chunk(BaseModel):
    id: str
    document_id: str
    chunk_id: str
    domain: str
    tenant_id: str = "default"
    doc_type: str = "kb"
    access_roles: list[str] = Field(default_factory=lambda: ["reader"])
    section_path: str = ""
    filename: str = ""
    page: int = 1
    text: str
    contextual_text: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=now_iso)
    updated_at: str = Field(default_factory=now_iso)

    @property
    def searchable_text(self) -> str:
        return self.contextual_text or self.text


class SearchFilters(BaseModel):
    tenant_id: str | None = None
    domain: str | None = None
    access_roles: list[str] | None = None
    doc_type: str | None = None


class SearchResult(BaseModel):
    chunk: Chunk
    score: float
    rank: int
    source: str = "dense"
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def chunk_id(self) -> str:
        return self.chunk.chunk_id

    def public_dict(self, include_text: bool = True) -> dict[str, Any]:
        data: dict[str, Any] = {
            "chunk_id": self.chunk.chunk_id,
            "document_id": self.chunk.document_id,
            "domain": self.chunk.domain,
            "tenant_id": self.chunk.tenant_id,
            "doc_type": self.chunk.doc_type,
            "access_roles": self.chunk.access_roles,
            "section_path": self.chunk.section_path,
            "filename": self.chunk.filename,
            "page": self.chunk.page,
            "score": self.score,
            "rank": self.rank,
            "source": self.source,
            "metadata": self.metadata,
        }
        if include_text:
            data["text"] = self.chunk.text
        return data


def candidate_k_for(top_k: int, has_domain_filter: bool) -> int:
    safe_top_k = max(int(top_k), 1)
    if has_domain_filter:
        return max(safe_top_k * 10, 50)
    return safe_top_k

