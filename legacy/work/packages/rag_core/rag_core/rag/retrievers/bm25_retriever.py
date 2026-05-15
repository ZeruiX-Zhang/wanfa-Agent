from __future__ import annotations

import math
from collections import Counter

from rag_core.rag.embedding import tokenize
from rag_core.rag.filters import chunk_matches_filters
from rag_core.rag.models import SearchFilters, SearchResult
from rag_core.rag.retrievers.base import BaseRetriever
from rag_core.rag.vector_stores.faiss_store import FaissVectorStore


class BM25Retriever(BaseRetriever):
    def __init__(self, vector_store: FaissVectorStore | None = None, k1: float = 1.5, b: float = 0.75) -> None:
        self.vector_store = vector_store or FaissVectorStore()
        self.k1 = k1
        self.b = b

    def retrieve(
        self,
        query: str,
        top_k: int,
        filters: SearchFilters | None = None,
    ) -> tuple[list[SearchResult], dict[str, object]]:
        chunks = [chunk for chunk in self.vector_store.list_chunks() if chunk_matches_filters(chunk, filters)]
        query_terms = tokenize(query)
        if not chunks or not query_terms:
            return [], {"candidate_count": len(chunks)}

        tokenized = [tokenize(chunk.searchable_text) for chunk in chunks]
        doc_freq: Counter[str] = Counter()
        for terms in tokenized:
            doc_freq.update(set(terms))

        doc_count = len(chunks)
        avgdl = sum(len(terms) for terms in tokenized) / max(doc_count, 1)
        scored: list[SearchResult] = []
        for chunk, terms in zip(chunks, tokenized, strict=True):
            term_counts = Counter(terms)
            doc_len = len(terms) or 1
            score = 0.0
            for term in query_terms:
                if term_counts[term] == 0:
                    continue
                idf = math.log(1 + (doc_count - doc_freq[term] + 0.5) / (doc_freq[term] + 0.5))
                numerator = term_counts[term] * (self.k1 + 1)
                denominator = term_counts[term] + self.k1 * (1 - self.b + self.b * doc_len / max(avgdl, 1))
                score += idf * numerator / denominator
            if score > 0:
                scored.append(SearchResult(chunk=chunk, score=score, rank=0, source="bm25"))

        scored.sort(key=lambda item: item.score, reverse=True)
        selected = scored[: max(top_k, 1)]
        for index, result in enumerate(selected, start=1):
            result.rank = index
        return selected, {"candidate_count": len(chunks)}


