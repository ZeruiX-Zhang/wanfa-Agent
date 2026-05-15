from __future__ import annotations

from rag_core.rag.models import Chunk, SearchFilters


def chunk_matches_filters(chunk: Chunk, filters: SearchFilters | None, include_domain: bool = True) -> bool:
    if filters is None:
        return True
    if filters.tenant_id and chunk.tenant_id != filters.tenant_id:
        return False
    if include_domain and filters.domain and chunk.domain != filters.domain:
        return False
    if filters.doc_type and chunk.doc_type != filters.doc_type:
        return False
    if filters.access_roles:
        chunk_roles = set(chunk.access_roles or [])
        if chunk_roles and chunk_roles.isdisjoint(filters.access_roles):
            return False
    return True


