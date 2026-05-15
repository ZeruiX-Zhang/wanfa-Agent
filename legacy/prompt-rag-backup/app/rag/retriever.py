from __future__ import annotations

from pathlib import Path

from app.core.config import settings
from app.llm.llm_client import LLMClient
from app.rag.vector_store import FaissVectorStore
from app.schemas.documents import RetrievedChunk


class Retriever:
    def __init__(
        self,
        project_root: Path | None = None,
        vector_store: FaissVectorStore | None = None,
        llm_client: LLMClient | None = None,
    ) -> None:
        self.project_root = (project_root or settings.project_root).resolve()
        self.vector_store = vector_store or FaissVectorStore(self.project_root / "storage" / "faiss")
        self.llm_client = llm_client or LLMClient()

    def retrieve(self, query: str, top_k: int = 5, domain: str | None = None) -> list[RetrievedChunk]:
        query_vector = self.llm_client.embed_texts([query])[0]
        return self.vector_store.search(query_vector=query_vector, top_k=top_k, domain=domain)
