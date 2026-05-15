from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.domain import DomainName


class IngestLocalRequest(BaseModel):
    domain: DomainName = "enterprise_kb"
    directory: str = Field(default="data/raw/enterprise_kb", min_length=1)
    glob_pattern: str = Field(default="**/*", min_length=1)
    build_index: bool = False


class DocumentMetadata(BaseModel):
    filename: str
    source: str
    path: str
    domain: DomainName = "enterprise_kb"
    scenario: str = "enterprise_knowledge_base"
    tenant_id: str = "demo_tenant"
    doc_type: str = "text"
    access_roles: list[str] = Field(default_factory=lambda: ["employee"])
    section_path: list[str] = Field(default_factory=list)
    page: int | None = None
    chunk_index: int


class DocumentChunk(BaseModel):
    chunk_id: str
    text: str
    metadata: DocumentMetadata


class IngestLocalResponse(BaseModel):
    success: bool
    documents_loaded: int
    chunks_created: int
    output_path: str
    index_built: bool = False
    trace_id: str


class RetrievedChunk(BaseModel):
    chunk_id: str
    text: str
    metadata: DocumentMetadata
    score: float
