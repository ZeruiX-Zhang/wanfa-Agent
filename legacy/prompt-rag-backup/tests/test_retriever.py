from __future__ import annotations

from app.rag.index_service import IndexService
from app.rag.retriever import Retriever
from app.rag.vector_store import FaissVectorStore
from app.schemas.documents import DocumentChunk, DocumentMetadata


class FakeLLMClient:
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in texts:
            lowered = text.lower()
            vectors.append(
                [
                    1.0 if "sla" in lowered or "p1" in lowered else 0.0,
                    1.0 if "\u62a5\u9500" in lowered or "\u9910\u996e" in lowered else 0.0,
                    1.0 if "sales" in lowered or "revenue" in lowered else 0.0,
                ]
            )
        return vectors


def _chunk(chunk_id: str, text: str, filename: str, domain: str = "enterprise_kb") -> DocumentChunk:
    return DocumentChunk(
        chunk_id=chunk_id,
        text=text,
        metadata=DocumentMetadata(
            filename=filename,
            source="local",
            path=f"data/raw/{domain}/{filename}",
            domain=domain,
            page=None,
            chunk_index=0,
        ),
    )


def test_faiss_retriever_returns_top_k(tmp_path):
    chunks_path = tmp_path / "data" / "processed" / "chunks.jsonl"
    chunks_path.parent.mkdir(parents=True)
    chunks = [
        _chunk("customer_support/sla.txt::0", "P1 SLA response is 15 minutes", "sla.txt", "customer_support"),
        _chunk("policy.md::0", "\u9910\u996e\u62a5\u9500\u4e0a\u9650\u662f 200 \u5143", "policy.md"),
        _chunk("sales.csv::0", "sales revenue report", "sales.csv"),
    ]
    chunks_path.write_text("\n".join(chunk.model_dump_json() for chunk in chunks) + "\n", encoding="utf-8")

    vector_store = FaissVectorStore(tmp_path / "storage" / "faiss")
    service = IndexService(project_root=tmp_path, chunks_path=chunks_path, vector_store=vector_store, llm_client=FakeLLMClient())
    indexed_count = service.build_index()

    retriever = Retriever(project_root=tmp_path, vector_store=vector_store, llm_client=FakeLLMClient())
    results = retriever.retrieve(
        "\u4f01\u4e1a\u5ba2\u6237 P1 SLA \u662f\u4ec0\u4e48\uff1f",
        top_k=2,
        domain="customer_support",
    )

    assert indexed_count == 3
    assert (tmp_path / "storage" / "faiss" / "index.faiss").exists()
    assert (tmp_path / "storage" / "faiss" / "chunks.jsonl").exists()
    assert len(results) == 1
    assert results[0].chunk_id == "customer_support/sla.txt::0"
    assert all(result.metadata.domain == "customer_support" for result in results)
