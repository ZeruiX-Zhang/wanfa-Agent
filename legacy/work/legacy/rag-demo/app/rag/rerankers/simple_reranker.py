from __future__ import annotations

from app.rag.embedding import tokenize
from app.rag.models import SearchResult
from app.rag.rerankers.base import BaseReranker


class SimpleReranker(BaseReranker):
    provider = "simple"

    def rerank(self, query: str, results: list[SearchResult], top_n: int) -> list[SearchResult]:
        query_terms = set(tokenize(query))
        reranked: list[SearchResult] = []
        for result in results:
            text_terms = set(tokenize(result.chunk.searchable_text))
            overlap = len(query_terms & text_terms)
            normalized_overlap = overlap / max(len(query_terms), 1)
            score = result.score + normalized_overlap
            reranked.append(
                SearchResult(
                    chunk=result.chunk,
                    score=score,
                    rank=0,
                    source="reranker",
                    metadata={
                        **result.metadata,
                        "reranker_provider": self.provider,
                        "original_source": result.source,
                        "original_score": result.score,
                        "term_overlap": overlap,
                    },
                )
            )
        reranked.sort(key=lambda item: item.score, reverse=True)
        selected = reranked[: max(top_n, 1)]
        for index, result in enumerate(selected, start=1):
            result.rank = index
        return selected

