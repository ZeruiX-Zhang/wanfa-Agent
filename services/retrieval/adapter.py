"""Minimal in-memory retrieval adapter for evidence-led queries."""

from __future__ import annotations

from typing import Iterable

from services.knowledge.models import EvidenceRecord, SourceRef
from services.retrieval.models import (
    RetrievalQuery,
    RetrievalResult,
    RetrievedEvidence,
)


class InMemoryRetrievalAdapter:
    """Search evidence records without mutating the source knowledge store."""

    def __init__(
        self,
        *,
        evidence: Iterable[EvidenceRecord] = (),
        sources: Iterable[SourceRef] = (),
    ) -> None:
        self._evidence = tuple(evidence)
        self._sources = {source.id: source for source in sources}

    def query(
        self,
        text: str,
        *,
        max_results: int = 5,
        min_trusted_evidence: int = 1,
        include_untrusted: bool = True,
    ) -> RetrievalResult:
        """Search evidence by simple text matching and return readiness flags."""

        if max_results <= 0:
            raise ValueError("max_results must be positive")
        query = RetrievalQuery(
            text=text,
            min_trusted_evidence=min_trusted_evidence,
            include_untrusted=include_untrusted,
        )
        normalized = text.casefold().strip()
        candidates: list[RetrievedEvidence] = []

        for entry in self._evidence:
            source = self._sources.get(entry.source_id)
            score = self._score(entry, source, normalized)
            if normalized and score <= 0:
                continue
            item = RetrievedEvidence.from_ledger(
                entry,
                source=source,
                score=score if normalized else 0.1,
            )
            if not include_untrusted and not item.usable_for_decision:
                continue
            candidates.append(item)

        candidates.sort(key=lambda item: item.score, reverse=True)
        items = tuple(candidates[:max_results])
        return RetrievalResult.from_items(query=query, items=items)

    def debug_snapshot(self) -> dict[str, int]:
        """Return a small non-sensitive snapshot for smoke/debug views."""

        return {
            "evidence_count": len(self._evidence),
            "source_count": len(self._sources),
        }

    def _score(
        self,
        entry: EvidenceRecord,
        source: SourceRef | None,
        normalized_query: str,
    ) -> float:
        if not normalized_query:
            return 0.0

        haystack_parts = [entry.claim, entry.excerpt]
        if source is not None:
            haystack_parts.append(source.title)
            if source.uri:
                haystack_parts.append(source.uri)
        haystack = " ".join(haystack_parts).casefold()

        if normalized_query in haystack:
            return 1.0

        query_terms = {
            term for term in normalized_query.split() if len(term) > 2
        }
        if not query_terms:
            return 0.0

        matched_terms = sum(1 for term in query_terms if term in haystack)
        return matched_terms / len(query_terms)
