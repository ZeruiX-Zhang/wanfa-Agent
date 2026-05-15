from __future__ import annotations

from rag_core.rag.models import SearchResult


def reciprocal_rank_fusion(
    result_sets: list[list[SearchResult]],
    top_k: int,
    rrf_k: int = 60,
) -> list[SearchResult]:
    fused_scores: dict[str, float] = {}
    representatives: dict[str, SearchResult] = {}
    component_ranks: dict[str, dict[str, int]] = {}

    for results in result_sets:
        for fallback_rank, result in enumerate(results, start=1):
            rank = result.rank or fallback_rank
            key = result.chunk.chunk_id
            fused_scores[key] = fused_scores.get(key, 0.0) + 1.0 / (rrf_k + rank)
            if key not in representatives or result.score > representatives[key].score:
                representatives[key] = result
            component_ranks.setdefault(key, {})[result.source] = rank

    ordered = sorted(fused_scores.items(), key=lambda item: item[1], reverse=True)
    fused: list[SearchResult] = []
    for rank, (chunk_id, score) in enumerate(ordered[: max(top_k, 1)], start=1):
        representative = representatives[chunk_id]
        fused.append(
            SearchResult(
                chunk=representative.chunk,
                score=score,
                rank=rank,
                source="hybrid",
                metadata={
                    "component_ranks": component_ranks.get(chunk_id, {}),
                    "representative_source": representative.source,
                },
            )
        )
    return fused


