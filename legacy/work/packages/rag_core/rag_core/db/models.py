from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class DocumentRecord:
    id: str
    tenant_id: str
    domain: str
    filename: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class IngestionJobRecord:
    id: str
    status: str
    documents_loaded: int = 0
    chunks_created: int = 0
    embeddings_created: int = 0
    error_message: str | None = None

