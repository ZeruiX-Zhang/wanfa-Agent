"""Minimal in-memory knowledge adapter for read projections and pending writes."""

from __future__ import annotations

from dataclasses import replace
from typing import Iterable

from services.knowledge.models import (
    EvidenceRecord,
    IntelligenceObject,
    KnowledgeItem,
    KnowledgeItemKind,
    KnowledgeSettings,
    KnowledgeWriteRequest,
    PendingKnowledgeWrite,
    ReviewStatus,
    SourceRef,
    new_id,
    utc_now,
)


class KnowledgeAdapterError(Exception):
    """Base error for knowledge adapter operations."""


class PendingWriteNotFound(KnowledgeAdapterError):
    """Raised when a pending write id is unknown."""


class PendingWriteAlreadyClosed(KnowledgeAdapterError):
    """Raised when an undo is attempted on a closed pending write."""


class InMemoryKnowledgeAdapter:
    """Read-mostly knowledge adapter with a pending review write queue.

    The adapter intentionally has no approve method. New content, including
    reflection and AI-generated material, can only be captured into
    ``pending_writes`` and cannot enter formal knowledge through this class.
    """

    def __init__(
        self,
        *,
        sources: Iterable[SourceRef] = (),
        evidence: Iterable[EvidenceRecord] = (),
        intelligence_objects: Iterable[IntelligenceObject] = (),
        formal_items: Iterable[KnowledgeItem] = (),
        settings: KnowledgeSettings | None = None,
    ) -> None:
        self._sources = {source.id: source for source in sources}
        self._evidence = {entry.id: entry for entry in evidence}
        self._intelligence_objects = {
            item.id: item for item in intelligence_objects
        }
        self._formal_items: dict[str, KnowledgeItem] = {}
        for item in formal_items:
            self._add_formal_seed(item)
        self._pending_writes: dict[str, PendingKnowledgeWrite] = {}
        self._settings = settings or KnowledgeSettings()

    def _add_formal_seed(self, item: KnowledgeItem) -> None:
        if not item.can_enter_formal_knowledge:
            raise ValueError(
                "Formal seed items must be approved non-AI, non-reflection knowledge."
            )
        self._formal_items[item.id] = item

    def list_sources(self) -> tuple[SourceRef, ...]:
        """Return source read projections."""

        return tuple(self._sources.values())

    def list_evidence(self) -> tuple[EvidenceRecord, ...]:
        """Return evidence ledger read projections."""

        return tuple(self._evidence.values())

    def list_intelligence_objects(self) -> tuple[IntelligenceObject, ...]:
        """Return derived intelligence object read projections."""

        return tuple(self._intelligence_objects.values())

    def get_settings(self) -> KnowledgeSettings:
        """Return read-only adapter settings."""

        return self._settings

    def list_formal_items(self) -> tuple[KnowledgeItem, ...]:
        """Return approved formal knowledge items only."""

        return tuple(self._formal_items.values())

    def submit_pending_write(
        self, request: KnowledgeWriteRequest
    ) -> PendingKnowledgeWrite:
        """Create a pending knowledge write.

        All writes are normalized to ``pending_review``. Reflection and
        AI-generated content remain pending and are not inserted into
        ``formal_items``.
        """

        item = KnowledgeItem(
            id=new_id("knowledge"),
            title=request.title,
            body=request.body,
            kind=request.kind,
            status=ReviewStatus.PENDING_REVIEW,
            source_ids=request.source_ids,
            evidence_ids=request.evidence_ids,
            submitted_by=request.submitted_by,
            generated_by_ai=request.generated_by_ai
            or request.kind is KnowledgeItemKind.AI_GENERATED,
            metadata=request.metadata,
        )
        pending_write = PendingKnowledgeWrite(
            id=new_id("pending"),
            item=item,
            reason=request.reason,
            submitted_by=request.submitted_by,
        )
        self._pending_writes[pending_write.id] = pending_write
        return pending_write

    def list_pending_writes(
        self, *, include_closed: bool = False
    ) -> tuple[PendingKnowledgeWrite, ...]:
        """Return pending write queue entries."""

        writes = tuple(self._pending_writes.values())
        if include_closed:
            return writes
        return tuple(
            write
            for write in writes
            if write.status is ReviewStatus.PENDING_REVIEW
        )

    def undo_pending_write(
        self, write_id: str, *, reason: str = "withdrawn by user"
    ) -> PendingKnowledgeWrite:
        """Withdraw a pending write before review."""

        pending_write = self._pending_writes.get(write_id)
        if pending_write is None:
            raise PendingWriteNotFound(f"Unknown pending write: {write_id}")
        if pending_write.status is not ReviewStatus.PENDING_REVIEW:
            raise PendingWriteAlreadyClosed(
                f"Pending write is already {pending_write.status.value}: {write_id}"
            )
        withdrawn = replace(
            pending_write,
            status=ReviewStatus.WITHDRAWN,
            closed_at=utc_now(),
            closed_reason=reason,
        )
        self._pending_writes[write_id] = withdrawn
        return withdrawn

    def get_source(self, source_id: str) -> SourceRef | None:
        """Return a source by id, if present."""

        return self._sources.get(source_id)

    def get_evidence(self, evidence_id: str) -> EvidenceRecord | None:
        """Return an evidence ledger entry by id, if present."""

        return self._evidence.get(evidence_id)
