from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.core.config import AGENT_CORE_ROOT
from app.db.session import can_connect, pg_connection
from app.rag.embedding import embed_text
from app.rag.models import Chunk, SearchFilters, SearchResult
from app.rag.vector_stores.base import BaseVectorStore


class PgVectorStore(BaseVectorStore):
    def ping(self) -> tuple[bool, str]:
        return can_connect()

    def apply_migrations(self) -> None:
        migration = AGENT_CORE_ROOT / "app" / "db" / "migrations" / "001_init_pgvector.sql"
        with pg_connection() as conn:
            conn.execute(migration.read_text(encoding="utf-8"))
            conn.commit()

    def replace_chunks(self, chunks: list[Chunk]) -> None:
        with pg_connection() as conn:
            conn.execute("TRUNCATE embeddings, chunks, documents RESTART IDENTITY CASCADE")
            conn.commit()
        self.upsert_chunks(chunks)

    def upsert_chunks(self, chunks: list[Chunk]) -> None:
        grouped: dict[str, list[Chunk]] = {}
        for chunk in chunks:
            grouped.setdefault(chunk.document_id, []).append(chunk)
        for document_id, document_chunks in grouped.items():
            first = document_chunks[0]
            self.upsert_document(
                document_id,
                {
                    "tenant_id": first.tenant_id,
                    "domain": first.domain,
                    "filename": first.filename,
                    "metadata": first.metadata,
                },
                document_chunks,
            )

    def upsert_document(self, document_id: str, metadata: dict[str, Any], chunks: list[Chunk]) -> None:
        with pg_connection() as conn:
            conn.execute(
                """
                INSERT INTO documents (id, tenant_id, domain, filename, metadata, updated_at)
                VALUES (%s, %s, %s, %s, %s::jsonb, now())
                ON CONFLICT (id) DO UPDATE SET
                    tenant_id = EXCLUDED.tenant_id,
                    domain = EXCLUDED.domain,
                    filename = EXCLUDED.filename,
                    metadata = EXCLUDED.metadata,
                    updated_at = now()
                """,
                (
                    document_id,
                    metadata.get("tenant_id", "default"),
                    metadata.get("domain", ""),
                    metadata.get("filename", ""),
                    json.dumps(metadata.get("metadata", {})),
                ),
            )
            for chunk in chunks:
                conn.execute(
                    """
                    INSERT INTO chunks (
                        id, document_id, chunk_id, domain, tenant_id, doc_type, access_roles,
                        section_path, filename, page, text, contextual_text, metadata, updated_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, now())
                    ON CONFLICT (chunk_id) DO UPDATE SET
                        domain = EXCLUDED.domain,
                        tenant_id = EXCLUDED.tenant_id,
                        doc_type = EXCLUDED.doc_type,
                        access_roles = EXCLUDED.access_roles,
                        section_path = EXCLUDED.section_path,
                        filename = EXCLUDED.filename,
                        page = EXCLUDED.page,
                        text = EXCLUDED.text,
                        contextual_text = EXCLUDED.contextual_text,
                        metadata = EXCLUDED.metadata,
                        updated_at = now()
                    """,
                    (
                        chunk.id,
                        chunk.document_id,
                        chunk.chunk_id,
                        chunk.domain,
                        chunk.tenant_id,
                        chunk.doc_type,
                        chunk.access_roles,
                        chunk.section_path,
                        chunk.filename,
                        chunk.page,
                        chunk.text,
                        chunk.contextual_text,
                        json.dumps(chunk.metadata),
                    ),
                )
                vector = "[" + ",".join(str(value) for value in embed_text(chunk.searchable_text)) + "]"
                conn.execute(
                    """
                    INSERT INTO embeddings (chunk_id, embedding)
                    VALUES (%s, %s::vector)
                    ON CONFLICT (chunk_id) DO UPDATE SET embedding = EXCLUDED.embedding
                    """,
                    (chunk.chunk_id, vector),
                )
            conn.commit()

    def delete_document(self, document_id: str) -> int:
        with pg_connection() as conn:
            cursor = conn.execute("DELETE FROM documents WHERE id = %s", (document_id,))
            conn.commit()
            return cursor.rowcount or 0

    def reindex_document(self, document_id: str, chunks: list[Chunk]) -> None:
        self.delete_document(document_id)
        self.upsert_chunks(chunks)

    def list_chunks(self) -> list[Chunk]:
        with pg_connection() as conn:
            rows = conn.execute(
                """
                SELECT id, document_id, chunk_id, domain, tenant_id, doc_type, access_roles,
                       section_path, filename, page, text, contextual_text, metadata,
                       created_at::text, updated_at::text
                FROM chunks
                ORDER BY chunk_id
                """
            ).fetchall()
        return [
            Chunk(
                id=row[0],
                document_id=row[1],
                chunk_id=row[2],
                domain=row[3],
                tenant_id=row[4],
                doc_type=row[5],
                access_roles=list(row[6] or []),
                section_path=row[7],
                filename=row[8],
                page=row[9],
                text=row[10],
                contextual_text=row[11],
                metadata=row[12] or {},
                created_at=row[13],
                updated_at=row[14],
            )
            for row in rows
        ]

    def search(
        self,
        query: str,
        top_k: int,
        filters: SearchFilters | None = None,
        candidate_k: int | None = None,
    ) -> tuple[list[SearchResult], dict[str, int]]:
        filters = filters or SearchFilters()
        vector = "[" + ",".join(str(value) for value in embed_text(query)) + "]"
        clauses = ["1=1"]
        params: list[Any] = [vector]
        if filters.tenant_id:
            clauses.append("c.tenant_id = %s")
            params.append(filters.tenant_id)
        if filters.domain:
            clauses.append("c.domain = %s")
            params.append(filters.domain)
        if filters.doc_type:
            clauses.append("c.doc_type = %s")
            params.append(filters.doc_type)
        if filters.access_roles:
            clauses.append("c.access_roles && %s")
            params.append(filters.access_roles)
        params.append(max(top_k, 1))
        sql = f"""
            SELECT c.id, c.document_id, c.chunk_id, c.domain, c.tenant_id, c.doc_type,
                   c.access_roles, c.section_path, c.filename, c.page, c.text,
                   c.contextual_text, c.metadata, 1 - (e.embedding <=> %s::vector) AS score
            FROM chunks c
            JOIN embeddings e ON e.chunk_id = c.chunk_id
            WHERE {' AND '.join(clauses)}
            ORDER BY e.embedding <=> %s::vector
            LIMIT %s
        """
        params.insert(1, vector)
        with pg_connection() as conn:
            rows = conn.execute(sql, params).fetchall()
        results: list[SearchResult] = []
        for rank, row in enumerate(rows, start=1):
            results.append(
                SearchResult(
                    chunk=Chunk(
                        id=row[0],
                        document_id=row[1],
                        chunk_id=row[2],
                        domain=row[3],
                        tenant_id=row[4],
                        doc_type=row[5],
                        access_roles=list(row[6] or []),
                        section_path=row[7],
                        filename=row[8],
                        page=row[9],
                        text=row[10],
                        contextual_text=row[11],
                        metadata=row[12] or {},
                    ),
                    score=float(row[13]),
                    rank=rank,
                    source="pgvector",
                )
            )
        return results, {
            "requested_top_k": max(top_k, 1),
            "candidate_k": candidate_k or max(top_k, 1),
            "before_filter_count": len(results),
            "after_filter_count": len(results),
        }

