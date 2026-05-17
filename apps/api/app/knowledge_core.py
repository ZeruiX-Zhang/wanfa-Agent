"""Production-grade knowledge core for Reality OS.

This module is the single source of truth for:

* **Absorption** — any new piece of knowledge (from browser capture, direct
  import, expert search, or memory note) enters the system through
  :meth:`KnowledgeCore.absorb`. The pipeline is: raw → clean → quality score →
  text index + vector index + concept graph. Nothing is created outside this
  method.
* **Ask** — :meth:`KnowledgeCore.ask` is the unified answer path. It chooses a
  thinking model, runs hybrid retrieval, assembles the evidence, scores answer
  quality, and returns either a grounded answer with citations or an explicit
  "insufficient evidence — here is what to look for next" guidance.
* **Prompt optimisation** — :meth:`KnowledgeCore.prompt_optimize` rewrites a
  user prompt using a deterministic top-expert pattern and optionally merges
  user memory preferences.
* **Memory** — :meth:`KnowledgeCore.memory_add` writes user preferences /
  decisions / notes through a mock-safe LLM filter so personal data does not
  leak into the text / vector stores unless approved.
* **Learning plan** — :meth:`KnowledgeCore.learn_plan` surfaces concepts that
  the user keeps retrieving but has low mastery on, and recommends the next
  study step.

The implementation stays self-contained (stdlib only) and deterministic: no
provider call is required to get meaningful output. Every function has clear
extension points for swapping in a real embedding model or a real LLM.
"""

from __future__ import annotations

import hashlib
import math
import re
import sqlite3
import threading
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Literal, Optional
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4

from . import audit_events
from .coaching_schema import apply_coaching_schema
from .mastery import MasteryState, decay, sm2_update
from .security_scanner import evidence_warning, flags_for_text


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


def _content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


_WORD_RE = re.compile(r"[\w\u4e00-\u9fff]+", re.UNICODE)


def tokenize(text: str) -> list[str]:
    if not text:
        return []
    tokens = [token.lower() for token in _WORD_RE.findall(text)]
    # Add character bigrams for Chinese runs so retrieval works even without
    # a full CJK segmenter.
    bigrams: list[str] = []
    for token in tokens:
        if any("\u4e00" <= ch <= "\u9fff" for ch in token):
            for index in range(len(token) - 1):
                bigrams.append(token[index : index + 2])
    tokens.extend(bigrams)
    return tokens


STOPWORDS = {
    "the", "and", "for", "with", "from", "that", "this", "into", "have",
    "has", "was", "were", "are", "its", "their", "will", "would", "could",
    "should", "been", "but", "not",
    "的", "了", "和", "是", "在", "也", "就", "都", "及", "等", "与",
}


# ---------------------------------------------------------------------------
# domain records
# ---------------------------------------------------------------------------


SourceKind = Literal[
    "browser_capture",
    "ai_answer_capture",
    "direct_import",
    "expert_search",
    "enterprise_cleanse",
    "memory_note",
]


QualityTier = Literal["verified", "needs_review", "insufficient", "rejected"]


ConflictState = Literal["none", "disputed", "superseded"]


@dataclass
class KnowledgeItem:
    id: str
    title: str
    body: str
    source_kind: SourceKind
    source_url: str | None
    created_at: str
    updated_at: str
    content_hash: str
    quality_score: float
    quality_tier: QualityTier
    tags: list[str]
    language: str
    tenant_id: str
    review_required: bool
    freshness_date: str | None
    accuracy_score: float
    veracity_score: float
    relevance_score: float
    concept_ids: list[str] = field(default_factory=list)
    # Step 0: Evidence governance fields
    applicability_scope: str | None = None
    conflict_state: ConflictState = "none"
    conflicts_with: list[str] = field(default_factory=list)
    security_flags: list[str] = field(default_factory=list)
    content_role: str = "evidence"
    snapshot_id: str | None = None
    excerpt_hash: str | None = None
    # Knowledge system optimization fields
    model_summary_id: str | None = None
    needs_refresh: bool = False
    validation_status: Literal["not_validated", "passed", "warning", "failed"] = "not_validated"

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "body": self.body,
            "source_kind": self.source_kind,
            "source_url": self.source_url,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "content_hash": self.content_hash,
            "quality_score": round(self.quality_score, 3),
            "quality_tier": self.quality_tier,
            "tags": list(self.tags),
            "language": self.language,
            "tenant_id": self.tenant_id,
            "review_required": self.review_required,
            "freshness_date": self.freshness_date,
            "accuracy_score": round(self.accuracy_score, 3),
            "veracity_score": round(self.veracity_score, 3),
            "relevance_score": round(self.relevance_score, 3),
            "concept_ids": list(self.concept_ids),
            "applicability_scope": self.applicability_scope,
            "conflict_state": self.conflict_state,
            "conflicts_with": list(self.conflicts_with),
            "security_flags": list(self.security_flags),
            "content_role": self.content_role,
            "snapshot_id": self.snapshot_id,
            "excerpt_hash": self.excerpt_hash,
            "model_summary_id": self.model_summary_id,
            "needs_refresh": self.needs_refresh,
            "validation_status": self.validation_status,
        }


@dataclass
class Concept:
    id: str
    label: str
    summary: str
    item_ids: list[str]
    neighbors: list[str]
    created_at: str
    # SM-2 mastery extension (R5.1, R5.6). All fields have backwards-compatible
    # defaults so existing call sites that build a ``Concept`` with only the
    # original six required fields keep working. The persisted columns are
    # added by ``apps.api.app.coaching_schema.apply_additive_columns`` and
    # match these defaults.
    mastery_score: float = 0.0
    last_practiced_at: str | None = None
    next_due_at: str | None = None
    decay_lambda: float = 0.05
    ef: float = 2.5
    repetition: int = 0
    interval_days: float = 0.0
    domain: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "summary": self.summary,
            "item_ids": list(self.item_ids),
            "neighbors": list(self.neighbors),
            "created_at": self.created_at,
            "mastery_score": self.mastery_score,
            "last_practiced_at": self.last_practiced_at,
            "next_due_at": self.next_due_at,
            "decay_lambda": self.decay_lambda,
            "ef": self.ef,
            "repetition": self.repetition,
            "interval_days": self.interval_days,
            "domain": self.domain,
        }


@dataclass
class MemoryNote:
    id: str
    text: str
    kind: Literal["preference", "decision", "journal"]
    tenant_id: str
    allow_into_knowledge_base: bool
    filter_reason: str
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "text": self.text,
            "kind": self.kind,
            "tenant_id": self.tenant_id,
            "allow_into_knowledge_base": self.allow_into_knowledge_base,
            "filter_reason": self.filter_reason,
            "created_at": self.created_at,
        }


@dataclass
class AnswerCitation:
    item_id: str
    title: str
    snippet: str
    url: str | None
    relevance: float
    quality: float
    security_flags: list[str] = field(default_factory=list)
    content_role: str = "evidence"
    snapshot_id: str | None = None
    excerpt_hash: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "item_id": self.item_id,
            "title": self.title,
            "snippet": self.snippet,
            "url": self.url,
            "relevance": round(self.relevance, 3),
            "quality": round(self.quality, 3),
            "security_flags": list(self.security_flags),
            "content_role": self.content_role,
            "snapshot_id": self.snapshot_id,
            "excerpt_hash": self.excerpt_hash,
        }


@dataclass
class EvidenceSnapshot:
    snapshot_id: str
    tenant_id: str
    source_url: str | None
    canonical_url: str | None
    title: str
    publisher: str | None
    author: str | None
    published_at: str | None
    fetched_at: str
    content_hash: str
    excerpt: str
    excerpt_hash: str
    surrounding_context: str
    credibility_score: float
    retrieval_score: float | None
    source_kind: str
    item_id: str | None = None
    security_flags: list[str] = field(default_factory=list)
    content_role: str = "evidence"

    def to_dict(self) -> dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "tenant_id": self.tenant_id,
            "source_url": self.source_url,
            "canonical_url": self.canonical_url,
            "title": self.title,
            "publisher": self.publisher,
            "author": self.author,
            "published_at": self.published_at,
            "fetched_at": self.fetched_at,
            "content_hash": self.content_hash,
            "excerpt": self.excerpt,
            "excerpt_hash": self.excerpt_hash,
            "surrounding_context": self.surrounding_context,
            "credibility_score": round(self.credibility_score, 3),
            "retrieval_score": round(self.retrieval_score, 3) if self.retrieval_score is not None else None,
            "source_kind": self.source_kind,
            "item_id": self.item_id,
            "security_flags": list(self.security_flags),
            "content_role": self.content_role,
        }


@dataclass
class AskResult:
    question: str
    language: str
    answer: str
    confidence: float
    confidence_band: Literal["solid", "probable", "uncertain", "insufficient"]
    thinking_model: str
    prompt_strategy: str
    citations: list[AnswerCitation]
    knowledge_gaps: list[str]
    next_actions: list[str]
    audit_id: str
    # Step 1: scaffold mode + acceptance check
    answer_mode: Literal["scaffold", "draft", "final"] = "scaffold"
    candidate_angles: list[str] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)
    key_tradeoffs: list[str] = field(default_factory=list)
    acceptance_check: dict[str, Any] = field(default_factory=dict)
    run_id: str | None = None
    evidence_snapshot_id: str | None = None
    evidence_snapshot_hash: str | None = None

    def to_dict(self) -> dict[str, Any]:
        result = {
            "run_id": self.run_id,
            "question": self.question,
            "language": self.language,
            "answer": self.answer,
            "confidence": round(self.confidence, 3),
            "confidence_band": self.confidence_band,
            "thinking_model": self.thinking_model,
            "prompt_strategy": self.prompt_strategy,
            "citations": [citation.to_dict() for citation in self.citations],
            "knowledge_gaps": list(self.knowledge_gaps),
            "next_actions": list(self.next_actions),
            "audit_id": self.audit_id,
            "answer_mode": self.answer_mode,
            "candidate_angles": list(self.candidate_angles),
            "open_questions": list(self.open_questions),
            "key_tradeoffs": list(self.key_tradeoffs),
            "acceptance_check": dict(self.acceptance_check),
            "evidence_snapshot_id": self.evidence_snapshot_id,
            "evidence_snapshot_hash": self.evidence_snapshot_hash,
        }
        return result


# ---------------------------------------------------------------------------
# thinking model catalogue (deterministic, transparent selection)
# ---------------------------------------------------------------------------


THINKING_MODELS: list[dict[str, Any]] = [
    {
        "id": "first_principles",
        "label_zh": "第一性原理",
        "label_en": "First principles",
        "triggers": ("为什么", "根本", "根因", "why", "root"),
    },
    {
        "id": "second_order",
        "label_zh": "二阶效应",
        "label_en": "Second-order effects",
        "triggers": ("影响", "后果", "副作用", "consequence", "side effect"),
    },
    {
        "id": "inversion",
        "label_zh": "反向思考",
        "label_en": "Inversion",
        "triggers": ("如何避免", "不该", "反而", "avoid", "prevent"),
    },
    {
        "id": "base_rate",
        "label_zh": "基准概率",
        "label_en": "Base rates",
        "triggers": ("概率", "多久", "一般", "typical", "rate"),
    },
    {
        "id": "expected_value",
        "label_zh": "期望值",
        "label_en": "Expected value",
        "triggers": ("值得", "划算", "收益", "should i", "roi"),
    },
    {
        "id": "ooda",
        "label_zh": "OODA 循环",
        "label_en": "OODA loop",
        "triggers": ("实时", "应对", "决策", "respond", "tactical"),
    },
    {
        "id": "cynefin",
        "label_zh": "Cynefin 框架",
        "label_en": "Cynefin",
        "triggers": ("复杂", "混乱", "不确定", "complex", "chaotic"),
    },
    {
        "id": "swot",
        "label_zh": "SWOT",
        "label_en": "SWOT",
        "triggers": ("优势", "劣势", "机会", "威胁", "strategy", "strategic"),
    },
]


def pick_thinking_model(question: str, language: str) -> dict[str, Any]:
    lower = question.lower()
    for model in THINKING_MODELS:
        if any(trigger in lower for trigger in model["triggers"]):
            return model
    return THINKING_MODELS[0]


# ---------------------------------------------------------------------------
# KnowledgeCore
# ---------------------------------------------------------------------------


class KnowledgeCore:
    """Production knowledge backbone. All state lives in a single SQLite DB."""

    SCHEMA_VERSION = 3

    def __init__(self, *, path: Path | str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._init_schema()

    # ---- schema ---------------------------------------------------------

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _init_schema(self) -> None:
        with self._lock, self._connect() as db:
            db.executescript(
                """
                create table if not exists knowledge_items (
                  id text primary key,
                  tenant_id text not null,
                  title text not null,
                  body text not null,
                  source_kind text not null,
                  source_url text,
                  content_hash text not null,
                  quality_score real not null,
                  quality_tier text not null,
                  accuracy_score real not null,
                  veracity_score real not null,
                  relevance_score real not null,
                  tags_json text not null default '[]',
                  language text not null default 'zh-CN',
                  review_required integer not null default 1,
                  freshness_date text,
                  applicability_scope text,
                  conflict_state text not null default 'none',
                  conflicts_with_json text not null default '[]',
                  security_flags_json text not null default '[]',
                  snapshot_id text,
                  excerpt_hash text,
                  model_summary_id text,
                  needs_refresh integer not null default 0,
                  validation_status text not null default 'not_validated',
                  created_at text not null,
                  updated_at text not null
                );

                create unique index if not exists idx_items_hash on knowledge_items(tenant_id, content_hash);

                create virtual table if not exists knowledge_items_fts
                  using fts5(title, body, tenant_id UNINDEXED, tokenize = 'unicode61');

                create table if not exists item_tokens (
                  item_id text not null,
                  token text not null,
                  weight real not null,
                  primary key (item_id, token)
                );

                create index if not exists idx_item_tokens_token on item_tokens(token);

                create table if not exists concepts (
                  id text primary key,
                  tenant_id text not null,
                  label text not null,
                  summary text not null,
                  created_at text not null
                );

                create table if not exists concept_item (
                  concept_id text not null,
                  item_id text not null,
                  primary key (concept_id, item_id)
                );

                create table if not exists concept_edges (
                  a text not null,
                  b text not null,
                  weight real not null default 1.0,
                  primary key (a, b)
                );

                create table if not exists memory_notes (
                  id text primary key,
                  tenant_id text not null,
                  text text not null,
                  kind text not null,
                  allow_into_knowledge_base integer not null default 0,
                  filter_reason text not null default '',
                  created_at text not null
                );

                create table if not exists audit_log (
                  id text primary key,
                  tenant_id text not null,
                  actor text not null,
                  action text not null,
                  subject text,
                  payload_json text,
                  created_at text not null
                );

                create index if not exists idx_audit_tenant on audit_log(tenant_id, created_at);

                create table if not exists learning_signals (
                  id integer primary key autoincrement,
                  tenant_id text not null,
                  concept_id text not null,
                  event text not null,
                  created_at text not null
                );

                create table if not exists evidence_snapshots (
                  snapshot_id text primary key,
                  tenant_id text not null,
                  source_url text,
                  canonical_url text,
                  title text not null default '',
                  publisher text,
                  author text,
                  published_at text,
                  fetched_at text not null,
                  content_hash text not null,
                  excerpt text not null,
                  excerpt_hash text not null,
                  surrounding_context text not null default '',
                  credibility_score real not null default 0.0,
                  retrieval_score real,
                  source_kind text not null,
                  item_id text,
                  security_flags_json text not null default '[]',
                  content_role text not null default 'evidence',
                  metadata_json text not null default '{}'
                );

                create index if not exists idx_evidence_snapshots_tenant
                on evidence_snapshots(tenant_id, fetched_at);

                create index if not exists idx_evidence_snapshots_hash
                on evidence_snapshots(tenant_id, source_url, content_hash);

                create table if not exists review_queue (
                  id text primary key,
                  tenant_id text not null,
                  knowledge_item_id text,
                  title text not null,
                  original_body text not null,
                  model_summary text,
                  divergence_score real not null default 0.0,
                  validation_result_json text not null default '{}',
                  status text not null default 'pending_review',
                  reviewer text,
                  reject_reason text,
                  created_at text not null,
                  reviewed_at text
                );

                create index if not exists idx_review_queue_tenant_status
                on review_queue(tenant_id, status, created_at);

                create table if not exists knowledge_summaries (
                  id text primary key,
                  tenant_id text not null,
                  item_id text not null,
                  core_viewpoint text not null,
                  applicable_scenario text not null,
                  key_constraints text not null,
                  full_summary text not null,
                  model_used text,
                  source text not null default 'deterministic',
                  divergence_score real not null default 0.0,
                  created_at text not null,
                  foreign key (item_id) references knowledge_items(id)
                );

                create index if not exists idx_knowledge_summaries_item
                on knowledge_summaries(item_id);

                create table if not exists concept_summaries (
                  id text primary key,
                  tenant_id text not null,
                  concept_id text not null,
                  summary text not null,
                  item_count integer not null,
                  model_used text,
                  created_at text not null,
                  foreign key (concept_id) references concepts(id)
                );

                create table if not exists query_history (
                  id text primary key,
                  tenant_id text not null,
                  query text not null,
                  domain_concepts text not null default '[]',
                  strategy_used text,
                  created_at text not null
                );

                create index if not exists idx_query_history_tenant
                on query_history(tenant_id, created_at);
                """
            )
            # Migrate: add columns if missing (for existing DBs)
            existing_cols = {row[1] for row in db.execute("pragma table_info(knowledge_items)").fetchall()}
            if "applicability_scope" not in existing_cols:
                db.execute("alter table knowledge_items add column applicability_scope text")
            if "conflict_state" not in existing_cols:
                db.execute("alter table knowledge_items add column conflict_state text not null default 'none'")
            if "conflicts_with_json" not in existing_cols:
                db.execute("alter table knowledge_items add column conflicts_with_json text not null default '[]'")
            if "security_flags_json" not in existing_cols:
                db.execute("alter table knowledge_items add column security_flags_json text not null default '[]'")
            if "snapshot_id" not in existing_cols:
                db.execute("alter table knowledge_items add column snapshot_id text")
            if "excerpt_hash" not in existing_cols:
                db.execute("alter table knowledge_items add column excerpt_hash text")
            if "model_summary_id" not in existing_cols:
                db.execute("alter table knowledge_items add column model_summary_id text")
            if "needs_refresh" not in existing_cols:
                db.execute("alter table knowledge_items add column needs_refresh integer not null default 0")
            if "validation_status" not in existing_cols:
                db.execute("alter table knowledge_items add column validation_status text not null default 'not_validated'")

            # Additive expert-coaching-loop schema (R12.1, R16.1). Runs in the
            # same transaction context so the new tables either all appear or
            # none do.
            apply_coaching_schema(db)

    # ---- absorption ----------------------------------------------------

    def absorb(
        self,
        *,
        tenant_id: str,
        title: str,
        body: str,
        source_kind: SourceKind,
        source_url: str | None = None,
        tags: Iterable[str] = (),
        freshness_date: str | None = None,
        language: str = "zh-CN",
        actor: str = "user",
        snapshot_id: str | None = None,
    ) -> KnowledgeItem:
        """Cleanse, score, index, and concept-link a new piece of knowledge."""

        body_clean = clean_body(body)
        title_clean = clean_title(title, body_clean)
        if not body_clean.strip():
            raise ValueError("absorb body is empty after cleaning")

        language = language or detect_language(body_clean)
        security_flags = flags_for_text(body_clean, source=source_kind)
        content_hash = _content_hash(f"{title_clean}\n{body_clean}")
        scores = score_quality(
            body=body_clean,
            source_kind=source_kind,
            freshness_date=freshness_date,
            has_url=bool(source_url),
        )
        tier: QualityTier = classify_tier(scores["quality_score"])
        review_required = tier in {"needs_review", "insufficient"} or source_kind in {
            "browser_capture",
            "ai_answer_capture",
            "memory_note",
        } or bool(security_flags)

        now = _utc_now_iso()

        with self._lock, self._connect() as db:
            snapshot = _load_evidence_snapshot(db, tenant_id, snapshot_id) if snapshot_id else None
            if snapshot is None:
                snapshot = _create_evidence_snapshot_row(
                    db,
                    tenant_id=tenant_id,
                    title=title_clean,
                    content=body_clean,
                    source_kind=source_kind,
                    source_url=source_url,
                    published_at=freshness_date,
                    credibility_score=scores["quality_score"],
                    retrieval_score=None,
                    item_id=None,
                    metadata={"actor": actor},
                )
            existing = db.execute(
                "select id from knowledge_items where tenant_id = ? and content_hash = ?",
                (tenant_id, content_hash),
            ).fetchone()
            if existing is not None:
                item_id = existing["id"]
                db.execute(
                    "update knowledge_items set updated_at = ?, snapshot_id = ?, excerpt_hash = ? where id = ?",
                    (now, snapshot.snapshot_id, snapshot.excerpt_hash, item_id),
                )
                db.execute(
                    "update evidence_snapshots set item_id = ? where tenant_id = ? and snapshot_id = ?",
                    (item_id, tenant_id, snapshot.snapshot_id),
                )
            else:
                item_id = _new_id("kn")
                # Step 0: derive applicability scope deterministically
                applicability_scope = _derive_applicability_scope(body_clean, source_kind)
                db.execute(
                    """
                    insert into knowledge_items(
                      id, tenant_id, title, body, source_kind, source_url,
                      content_hash, quality_score, quality_tier,
                      accuracy_score, veracity_score, relevance_score,
                      tags_json, language, review_required, freshness_date,
                      applicability_scope, conflict_state, conflicts_with_json, security_flags_json,
                      snapshot_id, excerpt_hash,
                      created_at, updated_at
                    ) values(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        item_id,
                        tenant_id,
                        title_clean,
                        body_clean,
                        source_kind,
                        source_url,
                        content_hash,
                        scores["quality_score"],
                        tier,
                        scores["accuracy_score"],
                        scores["veracity_score"],
                        scores["relevance_score"],
                        _json_tags(tags),
                        language,
                        1 if review_required else 0,
                        freshness_date,
                        applicability_scope,
                        "none",
                        "[]",
                        _json_tags(security_flags),
                        snapshot.snapshot_id,
                        snapshot.excerpt_hash,
                        now,
                        now,
                    ),
                )
                db.execute(
                    "update evidence_snapshots set item_id = ? where tenant_id = ? and snapshot_id = ?",
                    (item_id, tenant_id, snapshot.snapshot_id),
                )
                db.execute(
                    "insert into knowledge_items_fts(rowid, title, body, tenant_id) values((select rowid from knowledge_items where id = ?), ?, ?, ?)",
                    (item_id, title_clean, body_clean, tenant_id),
                )
                _index_tokens(db, item_id, f"{title_clean}\n{body_clean}")
                concept_ids = _attach_concepts(db, tenant_id, item_id, title_clean, body_clean, now)
                # Step 0: detect conflicts with existing items sharing concepts
                conflicts = _detect_conflicts(db, tenant_id, item_id, concept_ids, body_clean)
                conflicts_json = _json_tags(conflicts)
                conflict_state: ConflictState = "disputed" if conflicts else "none"
                db.execute(
                    "update knowledge_items set conflict_state = ?, conflicts_with_json = ? where id = ?",
                    (conflict_state, conflicts_json, item_id),
                )
                _log_audit(
                    db,
                    tenant_id,
                    actor,
                    "absorb",
                    item_id,
                    {"source_kind": source_kind, "security_flags": security_flags},
                )
                return self._hydrate_item(db, item_id, tenant_id, concept_ids)

            _log_audit(db, tenant_id, actor, "absorb_dedup", item_id, {"source_kind": source_kind})
            concepts = _concepts_for_item(db, item_id)
            return self._hydrate_item(db, item_id, tenant_id, concepts)

    def absorb_with_pipeline(
        self,
        *,
        tenant_id: str,
        title: str,
        body: str,
        source_kind: SourceKind,
        source_url: str | None = None,
        tags: Iterable[str] = (),
        freshness_date: str | None = None,
        language: str = "zh-CN",
        actor: str = "user",
        skip_model_summary: bool = False,
        skip_validation: bool = False,
        auto_approve: bool = False,
        run_id: str | None = None,
        divergence_threshold: float = 0.3,
    ) -> tuple[KnowledgeItem, dict[str, Any]]:
        """Enhanced absorption with model summary + Skill validation + quality gate.

        Pipeline flow:
        1. Security scan (for expert_search and browser_capture sources)
        2. Model summarization (unless skip_model_summary=True)
        3. Skill validation (unless skip_validation=True)
        4. Quality gate check (if divergence > threshold or critical severity)
        5. If auto_approve=True or no review needed, complete ingestion
        6. Otherwise, submit to review queue

        Returns:
            Tuple of (KnowledgeItem, pipeline_metadata) where pipeline_metadata
            contains summary_result, validation_result, review_status, trust_level,
            and security_scan_result.
        """
        import json as _json_mod
        from . import trace
        from .model_summarizer import ModelSummarizer, SummaryResult
        from .skill_validator import SkillValidator, ValidationResult
        from .quality_gate import QualityGate
        from .security_scanner import scan_text, has_blocking_finding, findings_to_dicts

        tags_list = list(tags)

        # --- Determine trust level based on source_kind ---
        trust_level: str
        if source_kind == "browser_capture":
            trust_level = "untrusted"
        elif source_kind == "direct_import":
            trust_level = "internal"
        elif source_kind == "expert_search":
            trust_level = "untrusted"
        else:
            trust_level = "untrusted"

        # --- Step 1: Security scan ---
        security_scan_result: dict[str, Any] = {
            "performed": False,
            "findings": [],
            "blocked": False,
        }

        # Security scan for sources that require it
        if source_kind in ("expert_search", "browser_capture"):
            findings = scan_text(body, source=source_kind)
            security_scan_result["performed"] = True
            security_scan_result["findings"] = findings_to_dicts(findings)
            security_scan_result["blocked"] = has_blocking_finding(findings)

            # Block ingestion if high/critical severity findings
            if has_blocking_finding(findings):
                # Still absorb but mark as review_required so it's not searchable
                item = self.absorb(
                    tenant_id=tenant_id,
                    title=title,
                    body=body,
                    source_kind=source_kind,
                    source_url=source_url,
                    tags=tags_list,
                    freshness_date=freshness_date,
                    language=language,
                    actor=actor,
                )
                # Update validation_status to failed
                with self._lock, self._connect() as db:
                    db.execute(
                        "UPDATE knowledge_items SET validation_status = 'failed', review_required = 1 WHERE id = ?",
                        (item.id,),
                    )
                item.validation_status = "failed"
                item.review_required = True

                trace.record_step(
                    run_id=run_id,
                    step_type="pipeline_security_block",
                    status="completed",
                    input_value={"title": title, "source_kind": source_kind},
                    output_value={"blocked": True, "findings_count": len(findings)},
                )

                pipeline_metadata: dict[str, Any] = {
                    "summary_result": None,
                    "validation_result": None,
                    "review_status": "blocked_by_security",
                    "trust_level": trust_level,
                    "security_scan_result": security_scan_result,
                }
                return item, pipeline_metadata

        # --- Step 2: Model summarization ---
        summary_result: SummaryResult | None = None
        if not skip_model_summary:
            summarizer = ModelSummarizer()
            summary_result = summarizer.summarize(
                title=title,
                body=body,
                source_kind=source_kind,
                language=language,
                run_id=run_id,
            )

        # --- Step 3: Skill validation ---
        validation_result: ValidationResult | None = None
        if not skip_validation:
            validator = SkillValidator()
            # For direct_import, skip source credibility check by not passing source_url
            # The validator internally trusts direct_import sources
            validation_result = validator.validate(
                item_title=title,
                item_body=body,
                source_kind=source_kind,
                tags=tags_list,
                freshness_date=freshness_date,
                source_url=source_url,
            )

            # For browser_capture: ensure completeness check is enforced
            # (already handled by the validator's completeness dimension)

        # --- Step 4: Determine if review is needed ---
        review_needed = False
        review_reasons: list[str] = []

        if summary_result and summary_result.divergence_score > divergence_threshold:
            review_needed = True
            review_reasons.append(
                f"divergence_score ({summary_result.divergence_score:.4f}) > threshold ({divergence_threshold})"
            )

        if validation_result and validation_result.overall_severity == "critical":
            review_needed = True
            review_reasons.append("validation severity is critical")

        # For expert_search: always require user confirmation
        if source_kind == "expert_search":
            review_needed = True
            review_reasons.append("expert_search requires user confirmation")

        # --- Step 5: Perform ingestion ---
        # Add validation warning tag if applicable
        effective_tags = list(tags_list)
        if validation_result and validation_result.overall_severity == "warning":
            if "validation_warning" not in effective_tags:
                effective_tags.append("validation_warning")

        item = self.absorb(
            tenant_id=tenant_id,
            title=title,
            body=body,
            source_kind=source_kind,
            source_url=source_url,
            tags=effective_tags,
            freshness_date=freshness_date,
            language=language,
            actor=actor,
        )

        # --- Save model summary to knowledge_summaries table ---
        summary_id: str | None = None
        if summary_result:
            summary_id = _new_id("sum")
            now = _utc_now_iso()
            with self._lock, self._connect() as db:
                db.execute(
                    """
                    INSERT INTO knowledge_summaries(
                        id, tenant_id, item_id, core_viewpoint, applicable_scenario,
                        key_constraints, full_summary, model_used, source,
                        divergence_score, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        summary_id,
                        tenant_id,
                        item.id,
                        summary_result.core_viewpoint,
                        summary_result.applicable_scenario,
                        summary_result.key_constraints,
                        summary_result.full_summary,
                        summary_result.model_used,
                        summary_result.source,
                        summary_result.divergence_score,
                        now,
                    ),
                )
                # Link summary to knowledge item
                db.execute(
                    "UPDATE knowledge_items SET model_summary_id = ? WHERE id = ?",
                    (summary_id, item.id),
                )
            item.model_summary_id = summary_id

        # --- Update validation status on the item ---
        if validation_result:
            validation_status: str
            if validation_result.overall_severity == "critical":
                validation_status = "failed"
            elif validation_result.overall_severity == "warning":
                validation_status = "warning"
            elif validation_result.passed:
                validation_status = "passed"
            else:
                validation_status = "failed"

            with self._lock, self._connect() as db:
                db.execute(
                    "UPDATE knowledge_items SET validation_status = ? WHERE id = ?",
                    (validation_status, item.id),
                )
            item.validation_status = validation_status  # type: ignore[assignment]

        # --- Step 6: Quality gate ---
        review_status: str
        if review_needed and not auto_approve:
            # Submit to review queue
            gate = QualityGate()
            gate.submit_for_review(
                tenant_id=tenant_id,
                knowledge_item_id=item.id,
                title=title,
                original_body=body,
                model_summary=summary_result.full_summary if summary_result else None,
                divergence_score=summary_result.divergence_score if summary_result else 0.0,
                validation_result=validation_result or ValidationResult(
                    passed=True,
                    dimensions=[],
                    skill_used=None,
                    overall_severity="pass",
                    warnings=[],
                    blocking_issues=[],
                ),
                actor=actor,
            )
            # Mark item as review_required
            with self._lock, self._connect() as db:
                db.execute(
                    "UPDATE knowledge_items SET review_required = 1 WHERE id = ?",
                    (item.id,),
                )
            item.review_required = True
            review_status = "pending_review"
        else:
            # Auto-approve or no review needed
            if review_needed and auto_approve:
                review_status = "auto_approved"
            else:
                review_status = "approved"
            # Mark item as not requiring review (if validation passed)
            if validation_result and validation_result.passed and not review_needed:
                with self._lock, self._connect() as db:
                    db.execute(
                        "UPDATE knowledge_items SET review_required = 0 WHERE id = ?",
                        (item.id,),
                    )
                item.review_required = False

        # --- Record pipeline completion to trace ---
        trace.record_step(
            run_id=run_id,
            step_type="absorb_with_pipeline",
            status="completed",
            input_value={
                "title": title,
                "source_kind": source_kind,
                "trust_level": trust_level,
            },
            output_value={
                "item_id": item.id,
                "review_status": review_status,
                "summary_source": summary_result.source if summary_result else None,
                "validation_passed": validation_result.passed if validation_result else None,
            },
        )

        # --- Build pipeline metadata ---
        pipeline_metadata = {
            "summary_result": summary_result.to_dict() if summary_result else None,
            "validation_result": {
                "passed": validation_result.passed,
                "overall_severity": validation_result.overall_severity,
                "dimensions": [
                    {
                        "name": d.name,
                        "passed": d.passed,
                        "score": round(d.score, 3),
                        "severity": d.severity,
                        "details": d.details,
                    }
                    for d in validation_result.dimensions
                ],
                "skill_used": validation_result.skill_used,
                "warnings": validation_result.warnings,
                "blocking_issues": validation_result.blocking_issues,
            } if validation_result else None,
            "review_status": review_status,
            "trust_level": trust_level,
            "security_scan_result": security_scan_result,
        }

        return item, pipeline_metadata

    # ---- retrieval -----------------------------------------------------

    def search(
        self,
        *,
        tenant_id: str,
        query: str,
        limit: int = 8,
    ) -> list[tuple[KnowledgeItem, float]]:
        """Hybrid BM25-ish FTS + TF-IDF vector similarity, with quality boost."""

        limit = max(1, min(limit, 50))
        query_clean = query.strip()
        if not query_clean:
            return []

        with self._lock, self._connect() as db:
            fts_rows = _fts_search(db, tenant_id, query_clean, limit * 3)
            tfidf_rows = _tfidf_search(db, tenant_id, query_clean, limit * 3)

            candidates: dict[str, dict[str, float]] = {}
            for row_id, score in fts_rows:
                candidates.setdefault(row_id, {"fts": 0.0, "vec": 0.0})["fts"] = score
            for row_id, score in tfidf_rows:
                candidates.setdefault(row_id, {"fts": 0.0, "vec": 0.0})["vec"] = score

            # Hybrid retrieval (Task 4.5, R8.2) is dark-launched behind
            # ``REALITY_OS_HYBRID_RETRIEVAL``. When off, the legacy fixed
            # 0.55/0.35/0.1 blend below runs verbatim — byte-identical
            # behaviour for existing callers (rollout plan).
            from . import feature_flags

            hybrid_on = feature_flags.hybrid_retrieval_enabled()
            hybrid_weights = None
            fts_lo = fts_hi = vec_lo = vec_hi = 0.0
            if hybrid_on:
                from .hybrid_retrieval import HybridWeights, normalize

                fts_vals = [p["fts"] for p in candidates.values()]
                vec_vals = [p["vec"] for p in candidates.values()]
                if fts_vals:
                    fts_lo, fts_hi = min(fts_vals), max(fts_vals)
                if vec_vals:
                    vec_lo, vec_hi = min(vec_vals), max(vec_vals)
                # The embed signal is not wired into ``core.search`` (it
                # lives in ``SqliteEmbedVectorStore``); ``embed_available``
                # is False so ``normalize`` reallocates its mass to
                # FTS/TF-IDF.
                hybrid_weights = normalize(HybridWeights(), embed_available=False)

            results: list[tuple[KnowledgeItem, float]] = []
            for item_id, parts in candidates.items():
                item = self._hydrate_item(db, item_id, tenant_id, None)
                if item is None:
                    continue
                if item.quality_tier == "rejected":
                    continue
                if hybrid_on and hybrid_weights is not None:
                    from .hybrid_retrieval import hybrid_score

                    fts_norm = _minmax_norm(parts["fts"], fts_lo, fts_hi)
                    vec_norm = _minmax_norm(parts["vec"], vec_lo, vec_hi)
                    blended = hybrid_score(fts_norm, vec_norm, 0.0, hybrid_weights)
                    blended = 0.9 * blended + 0.1 * item.quality_score
                else:
                    blended = 0.55 * parts["fts"] + 0.35 * parts["vec"] + 0.1 * item.quality_score
                if item.quality_tier == "insufficient":
                    blended *= 0.4
                # Step 3: Boost solo_thinking items (user's own unassisted reasoning)
                if "solo_thinking" in item.tags:
                    blended += 0.15
                results.append((item, blended))

        results.sort(key=lambda entry: entry[1], reverse=True)
        return results[:limit]

    def mark_needs_refresh(
        self,
        *,
        tenant_id: str,
        threshold_days: int = 90,
    ) -> list[str]:
        """Mark knowledge items whose freshness_date exceeds the threshold as needs_refresh.

        Scans all items for the tenant that have a freshness_date set, compares
        against (now - threshold_days), and sets needs_refresh=1 for stale items.
        Records the operation to audit_log.

        Returns:
            List of item IDs that were marked as needs_refresh.
        """
        from datetime import timedelta

        cutoff = datetime.now(timezone.utc) - timedelta(days=threshold_days)
        cutoff_iso = cutoff.isoformat()

        with self._lock, self._connect() as db:
            # Find items with freshness_date older than the cutoff that are not already marked
            rows = db.execute(
                """
                SELECT id FROM knowledge_items
                WHERE tenant_id = ?
                  AND freshness_date IS NOT NULL
                  AND freshness_date < ?
                  AND needs_refresh = 0
                """,
                (tenant_id, cutoff_iso),
            ).fetchall()

            marked_ids = [row["id"] for row in rows]

            if marked_ids:
                # Batch update
                db.execute(
                    f"""
                    UPDATE knowledge_items
                    SET needs_refresh = 1
                    WHERE tenant_id = ? AND id IN ({','.join('?' for _ in marked_ids)})
                    """,
                    [tenant_id] + marked_ids,
                )

            # Record to audit log
            _log_audit(
                db,
                tenant_id,
                "system",
                "mark_needs_refresh",
                None,
                {
                    "threshold_days": threshold_days,
                    "cutoff_iso": cutoff_iso,
                    "marked_count": len(marked_ids),
                    "marked_ids": marked_ids,
                },
            )

        return marked_ids

    def search_with_freshness_penalty(
        self,
        *,
        tenant_id: str,
        query: str,
        limit: int = 8,
    ) -> list[tuple[KnowledgeItem, float]]:
        """Search with a penalty applied to items marked as needs_refresh.

        Calls the standard search() method, then applies a 0.7 multiplier to
        the score of items where needs_refresh=True, re-sorts by adjusted score,
        and returns the top results.

        Returns:
            List of (KnowledgeItem, adjusted_score) tuples sorted by score descending.
        """
        FRESHNESS_PENALTY = 0.7

        results = self.search(tenant_id=tenant_id, query=query, limit=limit * 2)

        adjusted: list[tuple[KnowledgeItem, float]] = []
        for item, score in results:
            if item.needs_refresh:
                adjusted.append((item, score * FRESHNESS_PENALTY))
            else:
                adjusted.append((item, score))

        adjusted.sort(key=lambda entry: entry[1], reverse=True)
        return adjusted[:limit]

    # ---- ask -----------------------------------------------------------

    def ask(
        self,
        *,
        tenant_id: str,
        question: str,
        language: str = "zh-CN",
        mode: Literal["simple", "professional"] = "simple",
        model_tier: Literal["flagship", "mid", "basic", "insufficient"] = "flagship",
        actor: str = "user",
        answer_mode: Literal["scaffold", "draft", "final"] = "scaffold",
        task_contract: dict[str, Any] | None = None,
        run_id: str | None = None,
    ) -> AskResult:
        question = question.strip()
        if not question:
            raise ValueError("question is empty")

        from .trace import finish_run, record_acceptance_check, record_step, start_run

        run_id = run_id or start_run(
            tenant_id=tenant_id,
            user_id=actor,
            entrypoint="ask",
            input_value=question,
            metadata={
                "language": language,
                "mode": mode,
                "model_tier": model_tier,
                "answer_mode": answer_mode,
            },
        )
        thinking = pick_thinking_model(question, language)
        prompt_strategy = _prompt_strategy_for_tier(model_tier)
        record_step(
            run_id=run_id,
            step_type="thinking_route",
            input_value=question,
            output_value={"thinking_model": thinking["id"], "prompt_strategy": prompt_strategy},
            metadata={"thinking_model": thinking["id"]},
        )
        candidates = self.search(tenant_id=tenant_id, query=question, limit=6)

        citations: list[AnswerCitation] = []
        for item, relevance in candidates[:4]:
            snippet = evidence_warning(language) if item.security_flags else _derive_snippet(item.body, question)
            citations.append(
                AnswerCitation(
                    item_id=item.id,
                    title=item.title,
                    snippet=snippet,
                    url=item.source_url,
                    relevance=relevance,
                    quality=item.quality_score,
                    security_flags=item.security_flags,
                    content_role="evidence",
                    snapshot_id=item.snapshot_id,
                    excerpt_hash=item.excerpt_hash,
                )
            )
        record_step(
            run_id=run_id,
            step_type="retrieval",
            input_value=question,
            output_value=[citation.item_id for citation in citations],
            metadata={
                "candidate_count": len(candidates),
                "citation_count": len(citations),
                "flagged_citations": sum(1 for citation in citations if citation.security_flags),
            },
        )

        aggregate = _aggregate_confidence(citations)
        confidence_band: Literal["solid", "probable", "uncertain", "insufficient"]
        if aggregate >= 0.8 and len(citations) >= 2:
            confidence_band = "solid"
        elif aggregate >= 0.55:
            confidence_band = "probable"
        elif aggregate >= 0.3:
            confidence_band = "uncertain"
        else:
            confidence_band = "insufficient"

        knowledge_gaps: list[str] = []
        next_actions: list[str] = []
        if confidence_band == "insufficient":
            knowledge_gaps = derive_knowledge_gaps(question)
            next_actions = suggested_next_actions(question, language)

        # Step 1: Generate scaffold components (always computed)
        candidate_angles = _derive_candidate_angles(question, thinking, language)
        open_questions = _derive_open_questions(question, citations, language)
        key_tradeoffs = _derive_key_tradeoffs(question, language)

        # Step 1: Compose answer based on answer_mode
        if answer_mode == "scaffold":
            # Scaffold mode: no prose answer, only structured components
            answer = ""
        elif answer_mode == "draft":
            # Draft mode: answer with [?] markers on subjective claims
            answer = _compose_draft_answer(
                question=question,
                thinking=thinking,
                language=language,
                citations=citations,
                confidence_band=confidence_band,
                gaps=knowledge_gaps,
            )
        else:
            # Final mode: original behavior (only recommended for solid confidence)
            answer = _compose_answer(
                question=question,
                thinking=thinking,
                language=language,
                citations=citations,
                confidence_band=confidence_band,
                gaps=knowledge_gaps,
            )

        # Step 1: Acceptance check (L4 verification)
        acceptance_check = _run_acceptance_check(
            answer=answer,
            citations=citations,
            confidence_band=confidence_band,
            task_contract=task_contract,
            language=language,
            run_id=run_id,
        )
        record_acceptance_check(
            run_id=run_id,
            step_id=None,
            verdict=str(acceptance_check.get("verdict", "unknown")),
            verifier_used=bool(acceptance_check.get("verifier_used")),
            input_value={
                "citation_ids": [citation.item_id for citation in citations],
                "confidence_band": confidence_band,
            },
            output_value=acceptance_check,
            metadata={
                "truthfulness_passed": acceptance_check.get("truthfulness", {}).get("passed"),
                "goal_fit_passed": acceptance_check.get("goal_fit", {}).get("passed"),
            },
        )
        record_step(
            run_id=run_id,
            step_type="acceptance_check",
            input_value={"confidence_band": confidence_band, "citation_count": len(citations)},
            output_value=acceptance_check,
            verifier_used=bool(acceptance_check.get("verifier_used")),
            metadata={"verdict": acceptance_check.get("verdict")},
        )

        audit_id = self._record_audit(
            tenant_id=tenant_id,
            actor=actor,
            action="ask",
            subject=None,
            payload={
                "question_hash": _content_hash(question),
                "question_length": len(question),
                "language": language,
                "mode": mode,
                "model_tier": model_tier,
                "answer_mode": answer_mode,
                "citation_count": len(citations),
                "confidence_band": confidence_band,
                "confidence": aggregate,
                "thinking_model": thinking["id"],
                "acceptance_verdict": acceptance_check.get("verdict", "n/a"),
            },
        )

        for item, _ in candidates[: min(3, len(candidates))]:
            for concept_id in item.concept_ids:
                self._log_learning_signal(tenant_id, concept_id, "retrieved")

        result = AskResult(
            question=question,
            language=language,
            answer=answer,
            confidence=aggregate,
            confidence_band=confidence_band,
            thinking_model=thinking["label_zh"] if language == "zh-CN" else thinking["label_en"],
            prompt_strategy=prompt_strategy,
            citations=citations,
            knowledge_gaps=knowledge_gaps,
            next_actions=next_actions,
            audit_id=audit_id,
            answer_mode=answer_mode,
            candidate_angles=candidate_angles,
            open_questions=open_questions,
            key_tradeoffs=key_tradeoffs,
            acceptance_check=acceptance_check,
            run_id=run_id,
            evidence_snapshot_id=next((citation.snapshot_id for citation in citations if citation.snapshot_id), None),
            evidence_snapshot_hash=_content_hash(
                "|".join(
                    f"{citation.snapshot_id or ''}:{citation.excerpt_hash or ''}"
                    for citation in citations
                )
            ) if citations else None,
        )
        finish_run(
            run_id,
            output_value={
                "audit_id": audit_id,
                "confidence_band": confidence_band,
                "citation_count": len(citations),
                "acceptance_verdict": acceptance_check.get("verdict"),
            },
        )
        return result

    # ---- prompt --------------------------------------------------------

    def prompt_optimize(
        self,
        *,
        tenant_id: str,
        prompt: str,
        language: str = "zh-CN",
        include_memory: bool = True,
        actor: str = "user",
    ) -> dict[str, Any]:
        prompt = prompt.strip()
        if not prompt:
            raise ValueError("prompt is empty")

        memory_lines: list[str] = []
        if include_memory:
            memory_lines = self._preference_snippets(tenant_id, limit=5)

        thinking = pick_thinking_model(prompt, language)
        optimized = _rewrite_prompt(prompt, thinking, memory_lines, language)

        audit_id = self._record_audit(
            tenant_id=tenant_id,
            actor=actor,
            action="prompt_optimize",
            subject=None,
            payload={
                "length_in": len(prompt),
                "length_out": len(optimized),
                "thinking_model": thinking["id"],
                "memory_lines_used": len(memory_lines),
            },
        )
        return {
            "prompt_in": prompt,
            "prompt_out": optimized,
            "thinking_model": thinking["label_zh"] if language == "zh-CN" else thinking["label_en"],
            "memory_lines": memory_lines,
            "audit_id": audit_id,
        }

    # ---- memory --------------------------------------------------------

    def memory_add(
        self,
        *,
        tenant_id: str,
        text: str,
        kind: Literal["preference", "decision", "journal"] = "preference",
        actor: str = "user",
    ) -> MemoryNote:
        text = text.strip()
        if not text:
            raise ValueError("memory text is empty")
        allow, reason = memory_filter(text)
        note = MemoryNote(
            id=_new_id("mem"),
            text=text,
            kind=kind,
            tenant_id=tenant_id,
            allow_into_knowledge_base=allow,
            filter_reason=reason,
            created_at=_utc_now_iso(),
        )
        with self._lock, self._connect() as db:
            db.execute(
                """
                insert into memory_notes(id, tenant_id, text, kind, allow_into_knowledge_base, filter_reason, created_at)
                values(?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    note.id,
                    note.tenant_id,
                    note.text,
                    note.kind,
                    1 if note.allow_into_knowledge_base else 0,
                    note.filter_reason,
                    note.created_at,
                ),
            )
            _log_audit(db, tenant_id, actor, "memory_add", note.id, {"kind": kind, "allow": allow})
        return note

    def memory_list(self, *, tenant_id: str, limit: int = 50) -> list[MemoryNote]:
        with self._lock, self._connect() as db:
            rows = db.execute(
                "select * from memory_notes where tenant_id = ? order by created_at desc limit ?",
                (tenant_id, limit),
            ).fetchall()
        return [
            MemoryNote(
                id=row["id"],
                tenant_id=row["tenant_id"],
                text=row["text"],
                kind=row["kind"],  # type: ignore[arg-type]
                allow_into_knowledge_base=bool(row["allow_into_knowledge_base"]),
                filter_reason=row["filter_reason"],
                created_at=row["created_at"],
            )
            for row in rows
        ]

    # ---- learn ---------------------------------------------------------

    def learn_plan(self, *, tenant_id: str, language: str = "zh-CN", limit: int = 5) -> list[dict[str, Any]]:
        with self._lock, self._connect() as db:
            rows = db.execute(
                """
                select concept_id, count(*) as retrieved
                from learning_signals
                where tenant_id = ? and event = 'retrieved'
                group by concept_id
                order by retrieved desc
                limit ?
                """,
                (tenant_id, limit * 2),
            ).fetchall()
            if not rows:
                return []
            concept_map: dict[str, Concept] = {}
            for row in rows:
                concept = _load_concept(db, row["concept_id"])
                if concept:
                    concept_map[concept.id] = concept
            plans: list[dict[str, Any]] = []
            for row in rows:
                concept = concept_map.get(row["concept_id"])
                if not concept:
                    continue
                if len(concept.item_ids) == 0:
                    gap_level = "no_knowledge"
                elif len(concept.item_ids) < 2:
                    gap_level = "shallow"
                else:
                    gap_level = "consolidate"
                plans.append(
                    {
                        "concept_id": concept.id,
                        "label": concept.label,
                        "retrieved_count": int(row["retrieved"]),
                        "item_count": len(concept.item_ids),
                        "gap_level": gap_level,
                        "recommendation": _learning_recommendation(gap_level, concept, language),
                    }
                )
                if len(plans) >= limit:
                    break
            return plans

    def retrieval_practice_plan(
        self,
        *,
        tenant_id: str,
        language: str = "zh-CN",
        limit: int = 5,
        now: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """Generate retrieval practice exercises for SM-2 *due* concepts.

        Step 3: Scaffold-style feedback to combat capability degradation.
        Concepts are selected by the spaced-repetition scheduler --- only
        those whose ``next_due_at <= now`` (a NULL ``next_due_at`` is
        treated as due immediately) qualify (R5.3, Property 23) --- and
        returned in prerequisite-topological order. Each due concept
        yields a fixed format mix:

        - 3 cloze (fill-in-the-blank) questions from item bodies
        - 1 counterexample question (from concept neighbors)
        - 1 Socratic follow-up question
        """

        due = self.list_due_concepts(tenant_id=tenant_id, now=now)
        if not due:
            return []

        exercises: list[dict[str, Any]] = []
        with self._lock, self._connect() as db:
            for concept in due:
                if not concept.item_ids:
                    continue

                # Get the first item's body for cloze generation
                item_row = db.execute(
                    "select body, title from knowledge_items where id = ? and tenant_id = ?",
                    (concept.item_ids[0], tenant_id),
                ).fetchone()
                if not item_row:
                    continue

                body = item_row["body"]
                title = item_row["title"]

                exercises.append({
                    "concept_id": concept.id,
                    "label": concept.label,
                    "mastery_score": concept.mastery_score,
                    "next_due_at": concept.next_due_at,
                    "cloze_questions": _generate_cloze(body, concept.label, language),
                    "counterexample": _generate_counterexample(concept, language),
                    "socratic_question": _generate_socratic(concept.label, title, language),
                })
                if len(exercises) >= limit:
                    break

        return exercises

    # ---- library browsing ---------------------------------------------

    def library_stats(self, *, tenant_id: str) -> dict[str, Any]:
        with self._lock, self._connect() as db:
            totals = db.execute(
                """
                select
                  count(*) as total,
                  coalesce(sum(case when quality_tier = 'verified' then 1 else 0 end), 0) as verified,
                  coalesce(sum(case when review_required = 1 then 1 else 0 end), 0) as pending,
                  coalesce(sum(case when quality_tier = 'insufficient' then 1 else 0 end), 0) as insufficient
                from knowledge_items
                where tenant_id = ?
                """,
                (tenant_id,),
            ).fetchone()
            by_kind = db.execute(
                """
                select source_kind, count(*) as count
                from knowledge_items
                where tenant_id = ?
                group by source_kind
                order by count desc
                """,
                (tenant_id,),
            ).fetchall()
            concept_total = db.execute(
                "select count(*) as count from concepts where tenant_id = ?",
                (tenant_id,),
            ).fetchone()["count"]
            memory_total = db.execute(
                "select count(*) as count from memory_notes where tenant_id = ?",
                (tenant_id,),
            ).fetchone()["count"]
        return {
            "total": int(totals["total"] or 0),
            "verified": int(totals["verified"] or 0),
            "pending_review": int(totals["pending"] or 0),
            "insufficient": int(totals["insufficient"] or 0),
            "by_source": [{"source_kind": row["source_kind"], "count": int(row["count"])} for row in by_kind],
            "concepts": int(concept_total),
            "memory_notes": int(memory_total),
        }

    def library_list(
        self,
        *,
        tenant_id: str,
        limit: int = 50,
        offset: int = 0,
        source_kind: SourceKind | None = None,
        tier: QualityTier | None = None,
    ) -> list[KnowledgeItem]:
        with self._lock, self._connect() as db:
            where = ["tenant_id = ?"]
            params: list[Any] = [tenant_id]
            if source_kind:
                where.append("source_kind = ?")
                params.append(source_kind)
            if tier:
                where.append("quality_tier = ?")
                params.append(tier)
            query = f"""
                select * from knowledge_items
                where {' and '.join(where)}
                order by created_at desc
                limit ? offset ?
            """
            params.extend([limit, offset])
            rows = db.execute(query, params).fetchall()
            items: list[KnowledgeItem] = []
            for row in rows:
                concepts = _concepts_for_item(db, row["id"])
                items.append(_row_to_item(row, concepts))
        return items

    def library_get(self, *, tenant_id: str, item_id: str) -> KnowledgeItem | None:
        with self._lock, self._connect() as db:
            row = db.execute(
                "select * from knowledge_items where tenant_id = ? and id = ?",
                (tenant_id, item_id),
            ).fetchone()
            if row is None:
                return None
            concepts = _concepts_for_item(db, item_id)
            return _row_to_item(row, concepts)

    def create_evidence_snapshot(
        self,
        *,
        tenant_id: str,
        title: str,
        content: str,
        source_kind: SourceKind,
        source_url: str | None = None,
        canonical_url: str | None = None,
        publisher: str | None = None,
        author: str | None = None,
        published_at: str | None = None,
        credibility_score: float = 0.0,
        retrieval_score: float | None = None,
        item_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> EvidenceSnapshot:
        with self._lock, self._connect() as db:
            return _create_evidence_snapshot_row(
                db,
                tenant_id=tenant_id,
                title=title,
                content=content,
                source_kind=source_kind,
                source_url=source_url,
                canonical_url=canonical_url,
                publisher=publisher,
                author=author,
                published_at=published_at,
                credibility_score=credibility_score,
                retrieval_score=retrieval_score,
                item_id=item_id,
                metadata=metadata,
            )

    def get_evidence_snapshot(self, *, tenant_id: str, snapshot_id: str) -> EvidenceSnapshot | None:
        with self._lock, self._connect() as db:
            return _load_evidence_snapshot(db, tenant_id, snapshot_id)

    def approve_item(self, *, tenant_id: str, item_id: str, actor: str = "user") -> KnowledgeItem:
        with self._lock, self._connect() as db:
            row = db.execute(
                "select * from knowledge_items where tenant_id = ? and id = ?",
                (tenant_id, item_id),
            ).fetchone()
            if row is None:
                raise KeyError(item_id)
            db.execute(
                "update knowledge_items set review_required = 0, quality_tier = case when quality_tier = 'needs_review' then 'verified' else quality_tier end, updated_at = ? where id = ?",
                (_utc_now_iso(), item_id),
            )
            _log_audit(db, tenant_id, actor, "approve", item_id, {})
            return self._hydrate_item(db, item_id, tenant_id, None)

    def reject_item(self, *, tenant_id: str, item_id: str, actor: str = "user", reason: str = "") -> KnowledgeItem:
        with self._lock, self._connect() as db:
            row = db.execute(
                "select * from knowledge_items where tenant_id = ? and id = ?",
                (tenant_id, item_id),
            ).fetchone()
            if row is None:
                raise KeyError(item_id)
            db.execute(
                "update knowledge_items set review_required = 0, quality_tier = 'rejected', updated_at = ? where id = ?",
                (_utc_now_iso(), item_id),
            )
            _log_audit(db, tenant_id, actor, "reject", item_id, {"reason": reason})
            return self._hydrate_item(db, item_id, tenant_id, None)

    def list_concepts(self, *, tenant_id: str, limit: int = 40) -> list[Concept]:
        with self._lock, self._connect() as db:
            rows = db.execute(
                "select * from concepts where tenant_id = ? order by created_at desc limit ?",
                (tenant_id, limit),
            ).fetchall()
            concepts: list[Concept] = []
            for row in rows:
                item_ids = [r["item_id"] for r in db.execute(
                    "select item_id from concept_item where concept_id = ?",
                    (row["id"],),
                ).fetchall()]
                neighbours = [r["b"] for r in db.execute(
                    "select b from concept_edges where a = ? order by weight desc limit 5",
                    (row["id"],),
                ).fetchall()]
                concepts.append(
                    Concept(
                        id=row["id"],
                        label=row["label"],
                        summary=row["summary"],
                        item_ids=item_ids,
                        neighbors=neighbours,
                        created_at=row["created_at"],
                        **_concept_mastery_kwargs(row),
                    )
                )
        return [self.lazy_decay_on_read(concept) for concept in concepts]

    def load_concept(
        self, *, tenant_id: str, concept_id: str
    ) -> Concept | None:
        """Load a single :class:`Concept` with lazy decay applied on read.

        Returns ``None`` if the concept does not exist for ``tenant_id``.
        The returned object's ``mastery_score`` reflects exponential decay
        since ``last_practiced_at`` (R5.5, R5.6); the persisted value is
        not modified by this call.
        """

        with self._lock, self._connect() as db:
            row = db.execute(
                "select * from concepts where tenant_id = ? and id = ?",
                (tenant_id, concept_id),
            ).fetchone()
            if row is None:
                return None
            item_ids = [r["item_id"] for r in db.execute(
                "select item_id from concept_item where concept_id = ?",
                (concept_id,),
            ).fetchall()]
            neighbours = [r["b"] for r in db.execute(
                "select b from concept_edges where a = ? order by weight desc limit 5",
                (concept_id,),
            ).fetchall()]
            concept = Concept(
                id=row["id"],
                label=row["label"],
                summary=row["summary"],
                item_ids=item_ids,
                neighbors=neighbours,
                created_at=row["created_at"],
                **_concept_mastery_kwargs(row),
            )
        return self.lazy_decay_on_read(concept)

    def lazy_decay_on_read(
        self, concept: Concept, *, now: datetime | None = None
    ) -> Concept:
        """Return a new :class:`Concept` with ``mastery_score`` decayed in memory.

        Implements R5.6's lazy-decay-on-read contract: the recomputed value
        is **not** persisted by this method. The caller's same-turn write
        path (e.g. :meth:`grade_concept`) is what triggers a persist.

        ``now`` defaults to ``datetime.now(timezone.utc)``. When the concept
        has never been practiced (``last_practiced_at is None``) or its
        ``decay_lambda`` is non-positive, the input is returned unchanged.
        """

        if not concept.last_practiced_at or concept.decay_lambda <= 0:
            return concept
        try:
            last = _parse_iso(concept.last_practiced_at)
        except ValueError:
            return concept
        current = now or datetime.now(timezone.utc)
        dt_seconds = (current - last).total_seconds()
        if dt_seconds <= 0:
            return concept
        dt_days = dt_seconds / 86400.0
        try:
            decayed = decay(concept.mastery_score, concept.decay_lambda, dt_days)
        except ValueError:
            return concept
        if decayed >= concept.mastery_score:
            return concept
        return replace(concept, mastery_score=decayed)

    def grade_concept(
        self,
        *,
        tenant_id: str,
        concept_id: str,
        grade: int,
        actor: str = "user",
        now: datetime | None = None,
        source: str = "practice",
    ) -> Concept:
        """Apply an SM-2 practice grade to a concept and persist the result.

        Loads the current row, builds a :class:`MasteryState` from it,
        runs :func:`sm2_update`, writes the new fields back to the
        ``concepts`` table, appends a row to ``mastery_history``, and
        emits a single ``mastery_update`` audit entry whose payload keys
        match R13.2 (``concept_id, prev, next, source, grade``).

        Raises ``KeyError`` if the concept does not exist for the tenant
        and ``ValueError`` if ``grade`` is outside ``0..5``.
        """

        if not (0 <= grade <= 5):
            raise ValueError(f"grade must be in 0..5, got {grade!r}")

        current = now or datetime.now(timezone.utc)

        with self._lock, self._connect() as db:
            row = db.execute(
                "select * from concepts where tenant_id = ? and id = ?",
                (tenant_id, concept_id),
            ).fetchone()
            if row is None:
                raise KeyError(concept_id)

            kwargs = _concept_mastery_kwargs(row)
            prev_score = float(kwargs.get("mastery_score", 0.0))
            prev_ef = float(kwargs.get("ef", 2.5))
            prev_repetition = int(kwargs.get("repetition", 0))
            prev_interval_days = float(kwargs.get("interval_days", 0.0))
            prev_decay_lambda = float(kwargs.get("decay_lambda", 0.05)) or 0.05
            last_practiced_raw = kwargs.get("last_practiced_at")
            try:
                last_practiced_dt = (
                    _parse_iso(last_practiced_raw) if last_practiced_raw else current
                )
            except ValueError:
                last_practiced_dt = current
            try:
                next_due_dt = _parse_iso(kwargs["next_due_at"]) if kwargs.get("next_due_at") else last_practiced_dt
            except ValueError:
                next_due_dt = last_practiced_dt

            prev_state = MasteryState(
                mastery_score=prev_score,
                ef=prev_ef,
                repetition=prev_repetition,
                interval_days=prev_interval_days,
                last_practiced_at=last_practiced_dt,
                next_due_at=next_due_dt,
                decay_lambda=prev_decay_lambda,
            )
            next_state = sm2_update(grade, prev_state, current)

            last_practiced_iso = next_state.last_practiced_at.isoformat()
            next_due_iso = next_state.next_due_at.isoformat()
            now_iso = _utc_now_iso()

            db.execute(
                """
                update concepts set
                  mastery_score = ?,
                  last_practiced_at = ?,
                  next_due_at = ?,
                  decay_lambda = ?,
                  ef = ?,
                  repetition = ?,
                  interval_days = ?
                where tenant_id = ? and id = ?
                """,
                (
                    next_state.mastery_score,
                    last_practiced_iso,
                    next_due_iso,
                    next_state.decay_lambda,
                    next_state.ef,
                    next_state.repetition,
                    next_state.interval_days,
                    tenant_id,
                    concept_id,
                ),
            )
            db.execute(
                """
                insert into mastery_history(
                  id, tenant_id, concept_id, prev_score, next_score,
                  source, grade, created_at
                ) values (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    _new_id("mh"),
                    tenant_id,
                    concept_id,
                    prev_score,
                    next_state.mastery_score,
                    source,
                    grade,
                    now_iso,
                ),
            )
            _log_audit(
                db,
                tenant_id,
                actor,
                audit_events.MASTERY_UPDATE,
                concept_id,
                {
                    "concept_id": concept_id,
                    "prev": prev_score,
                    "next": next_state.mastery_score,
                    "source": source,
                    "grade": grade,
                },
            )

            # Reload the freshly persisted row in the same connection. We
            # skip lazy decay here: the practice we just wrote is the most
            # recent signal, so the persisted value already reflects the
            # current mastery_score.
            row = db.execute(
                "select * from concepts where tenant_id = ? and id = ?",
                (tenant_id, concept_id),
            ).fetchone()
            item_ids = [r["item_id"] for r in db.execute(
                "select item_id from concept_item where concept_id = ?",
                (concept_id,),
            ).fetchall()]
            neighbours = [r["b"] for r in db.execute(
                "select b from concept_edges where a = ? order by weight desc limit 5",
                (concept_id,),
            ).fetchall()]

        return Concept(
            id=row["id"],
            label=row["label"],
            summary=row["summary"],
            item_ids=item_ids,
            neighbors=neighbours,
            created_at=row["created_at"],
            **_concept_mastery_kwargs(row),
        )

    def list_due_concepts(
        self,
        *,
        tenant_id: str,
        now: datetime | None = None,
        limit: int | None = None,
    ) -> list[Concept]:
        """Return concepts whose ``next_due_at <= now`` in topological order.

        Concepts whose ``next_due_at`` is NULL are treated as due
        immediately (R5.3). Ordering is computed from the
        ``concept_prerequisites`` edges so a parent (prerequisite) is
        always returned before any of its children. Concepts with no
        prereqs come first.

        ``limit`` is applied to the **due** result set after topological
        sort. ``now`` defaults to ``datetime.now(timezone.utc)``.
        """

        current = now or datetime.now(timezone.utc)
        cutoff_iso = current.isoformat()

        with self._lock, self._connect() as db:
            rows = db.execute(
                """
                select * from concepts
                where tenant_id = ?
                  and (next_due_at is null or next_due_at <= ?)
                """,
                (tenant_id, cutoff_iso),
            ).fetchall()
            due_ids = {row["id"] for row in rows}
            edges = db.execute(
                """
                select parent_concept_id as parent, child_concept_id as child
                from concept_prerequisites
                where tenant_id = ?
                """,
                (tenant_id,),
            ).fetchall()
            row_by_id: dict[str, sqlite3.Row] = {row["id"]: row for row in rows}
            adjacency: dict[str, list[str]] = {cid: [] for cid in due_ids}
            indegree: dict[str, int] = {cid: 0 for cid in due_ids}
            for edge in edges:
                parent = edge["parent"]
                child = edge["child"]
                if parent in due_ids and child in due_ids:
                    adjacency[parent].append(child)
                    indegree[child] = indegree.get(child, 0) + 1

            ordered_ids = _topological_order(due_ids, adjacency, indegree, row_by_id)

            concepts: list[Concept] = []
            for concept_id in ordered_ids:
                row = row_by_id[concept_id]
                item_ids = [r["item_id"] for r in db.execute(
                    "select item_id from concept_item where concept_id = ?",
                    (concept_id,),
                ).fetchall()]
                neighbours = [r["b"] for r in db.execute(
                    "select b from concept_edges where a = ? order by weight desc limit 5",
                    (concept_id,),
                ).fetchall()]
                concepts.append(
                    Concept(
                        id=row["id"],
                        label=row["label"],
                        summary=row["summary"],
                        item_ids=item_ids,
                        neighbors=neighbours,
                        created_at=row["created_at"],
                        **_concept_mastery_kwargs(row),
                    )
                )
        decayed = [self.lazy_decay_on_read(concept) for concept in concepts]
        if limit is not None:
            return decayed[: max(0, int(limit))]
        return decayed

    def _concept_vector(
        self, db: sqlite3.Connection, tenant_id: str, concept_id: str
    ) -> list[float] | None:
        """Average the stored vectors of a concept's linked items (R8.3).

        Returns ``None`` when no linked item carries an embedding, which
        is how the analogy surface degrades when the embed layer is off.
        """

        from .vector_store import decode_vector

        item_rows = db.execute(
            "select item_id from concept_item where concept_id = ?",
            (concept_id,),
        ).fetchall()
        vectors: list[list[float]] = []
        for item_row in item_rows:
            row = db.execute(
                "select vector from knowledge_items where tenant_id = ? and id = ?",
                (tenant_id, item_row["item_id"]),
            ).fetchone()
            if row is not None and row["vector"]:
                vectors.append(decode_vector(row["vector"]))
        if not vectors:
            return None
        dim = min(len(v) for v in vectors)
        return [sum(v[i] for v in vectors) / len(vectors) for i in range(dim)]

    def find_analogies(
        self,
        *,
        tenant_id: str,
        concept_id: str,
        limit: int = 5,
    ) -> dict[str, Any] | None:
        """Cross-domain analogies for a concept, cosine-ranked (R8.3).

        Returns ``None`` when the source concept does not exist for this
        tenant (so the caller can answer 404 without leaking existence).
        ``analogies_available`` is ``False`` when the source concept --- or
        every cross-domain candidate --- lacks a stored embedding, which
        is the case whenever the embed layer is disabled.
        """

        from .vector_store import rank_analogies

        with self._lock, self._connect() as db:
            source = db.execute(
                "select id, domain from concepts where tenant_id = ? and id = ?",
                (tenant_id, concept_id),
            ).fetchone()
            if source is None:
                return None
            source_domain = source["domain"]
            source_vector = self._concept_vector(db, tenant_id, concept_id)

            candidates: list[dict[str, Any]] = []
            other_rows = db.execute(
                "select id, label, domain from concepts "
                "where tenant_id = ? and id != ?",
                (tenant_id, concept_id),
            ).fetchall()
            for row in other_rows:
                candidates.append(
                    {
                        "concept_id": row["id"],
                        "label": row["label"],
                        "domain": row["domain"],
                        "vector": self._concept_vector(db, tenant_id, row["id"]),
                    }
                )

        analogies = rank_analogies(
            source_domain=source_domain,
            source_vector=source_vector,
            candidates=candidates,
            limit=limit,
        )
        available = source_vector is not None and bool(analogies)
        return {
            "source_concept_id": concept_id,
            "source_domain": source_domain,
            "analogies_available": available,
            "analogies": analogies if available else [],
        }

    def record_experiment_review(
        self,
        *,
        tenant_id: str,
        experiment_id: str,
        result_class: str,
        key_metrics: list[dict[str, Any]] | None = None,
        notes: str = "",
        concept_ids: list[str] | None = None,
        actor: str = "user",
        now: datetime | None = None,
    ) -> dict[str, Any]:
        """Persist a structured experiment review + hard-bind mastery (R9.1, R9.2).

        Every concept in ``concept_ids`` is graded via :meth:`grade_concept`
        with the SM-2 grade derived from ``result_class``
        (``success=5, partial=3, fail=1``) and ``source="experiment_review"``
        so the mastery curve reflects real-world outcomes (R9.2). A
        single ``experiment_review.recorded`` audit row is emitted.

        Concepts that do not exist for the tenant are skipped rather than
        aborting the whole review, so a partially-stale ``concept_ids``
        list still records the review and binds the concepts that remain.
        """

        import json as _json

        from .mastery import grade_to_sm2
        from .reality_layers import ExperimentReview, KeyMetric

        current = now or datetime.now(timezone.utc)
        review_id = _new_id("exr")
        metrics = [KeyMetric.from_dict(m) for m in (key_metrics or [])]
        review = ExperimentReview(
            id=review_id,
            tenant_id=tenant_id,
            experiment_id=experiment_id,
            result_class=result_class,  # type: ignore[arg-type]
            key_metrics=metrics,
            notes=notes or "",
            created_at=current.isoformat(),
        )

        with self._lock, self._connect() as db:
            db.execute(
                """
                insert into experiment_reviews(
                  id, tenant_id, experiment_id, result_class,
                  key_metrics_json, metric_breach, notes, created_at
                ) values (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    review_id,
                    tenant_id,
                    experiment_id,
                    result_class,
                    _json.dumps(
                        [m.to_dict() for m in metrics], ensure_ascii=False
                    ),
                    1 if review.metric_breach else 0,
                    notes or "",
                    current.isoformat(),
                ),
            )

        # Mastery hard-binding: grade every linked concept (R9.2).
        grade = grade_to_sm2(result_class)  # type: ignore[arg-type]
        graded: list[str] = []
        for concept_id in concept_ids or []:
            try:
                self.grade_concept(
                    tenant_id=tenant_id,
                    concept_id=concept_id,
                    grade=grade,
                    actor=actor,
                    now=current,
                    source="experiment_review",
                )
                graded.append(concept_id)
            except KeyError:
                # Stale concept id — skip, but keep recording the review.
                continue

        self._record_audit(
            tenant_id=tenant_id,
            actor=actor,
            action=audit_events.EXPERIMENT_REVIEW_RECORDED,
            subject=experiment_id,
            payload={
                "experiment_id": experiment_id,
                "result_class": result_class,
                "graded_concepts": graded,
                "metric_breach": review.metric_breach,
            },
        )

        return {"review": review.to_dict(), "graded_concepts": graded}

    def recent_experiment_result_classes(
        self, *, tenant_id: str, limit: int = 20
    ) -> list[str]:
        """Return the tenant's recent experiment ``result_class`` values.

        Ordered oldest-to-newest within the most-recent ``limit`` rows so
        :func:`skill_chain.count_trailing_fails` can read the trailing
        failure streak straight off the tail (R9.3).
        """

        with self._lock, self._connect() as db:
            rows = db.execute(
                "select result_class from experiment_reviews "
                "where tenant_id = ? order by created_at desc limit ?",
                (tenant_id, max(1, limit)),
            ).fetchall()
        return [row["result_class"] for row in reversed(rows)]

    # ---- learning dashboard (Task 5.1-5.4, R10, read-only) ------------

    def dashboard_mastery(self, *, tenant_id: str) -> dict[str, Any]:
        """Mastery heatmap grouped by concept domain (R10.1.a, R10.6)."""

        concepts = self.list_concepts(tenant_id=tenant_id)
        groups: dict[str, list[Concept]] = {}
        for concept in concepts:
            key = concept.domain or "uncategorised"
            groups.setdefault(key, []).append(concept)

        domains: list[dict[str, Any]] = []
        for domain in sorted(groups):
            members = groups[domain]
            scores = [c.mastery_score for c in members]
            domains.append(
                {
                    "domain": domain,
                    "count": len(members),
                    "avg_mastery": sum(scores) / len(scores) if scores else 0.0,
                    "concepts": [
                        {
                            "id": c.id,
                            "label": c.label,
                            "mastery_score": c.mastery_score,
                            "next_due_at": c.next_due_at,
                        }
                        for c in members
                    ],
                }
            )
        return {"domains": domains, "concept_count": len(concepts)}

    def dashboard_calibration(self, *, tenant_id: str) -> dict[str, Any]:
        """Calibration curve + Brier score for the tenant (R10.1.b)."""

        from . import calibration as calibration_mod

        records = calibration_mod.list_calibration_records(
            core=self, tenant_id=tenant_id
        )
        resolved = [
            r
            for r in records
            if r.brier_score is not None and r.binary_value is not None
        ]
        preds = [float(r.confidence) for r in resolved]
        outcomes = [int(r.binary_value) for r in resolved]  # type: ignore[arg-type]

        bins = calibration_mod.calibration_curve(preds, outcomes) if resolved else []
        brier = calibration_mod.brier_score(preds, outcomes) if resolved else None
        return {
            "calibration_score": calibration_mod.calibration_score(records),
            "brier_score": brier,
            "resolved_count": len(resolved),
            "total_count": len(records),
            "bins": [
                {
                    "lo": b.lo,
                    "hi": b.hi,
                    "count": b.count,
                    "mean_pred": b.mean_pred,
                    "empirical_freq": b.empirical_freq,
                }
                for b in bins
            ],
        }

    def dashboard_skill_chain(self, *, tenant_id: str) -> dict[str, Any]:
        """Skill-chain completion rate grouped by problem_type (R10.1.c)."""

        from . import skill_chain as skill_chain_mod

        # Ensure the chain definitions are loaded so ``get_chain`` resolves
        # problem_type + step counts (idempotent — skips loaded paths).
        skill_chain_mod.load_all()

        with self._lock, self._connect() as db:
            rows = db.execute(
                "select chain_id, step_idx from skill_chains_state "
                "where tenant_id = ?",
                (tenant_id,),
            ).fetchall()

        by_type: dict[str, list[float]] = {}
        step_reach: dict[str, list[int]] = {}
        for row in rows:
            chain = skill_chain_mod.get_chain(row["chain_id"])
            if chain is None:
                continue
            total = max(len(chain.steps), 1)
            problem_type = chain.problem_type
            completion = min(1.0, (int(row["step_idx"]) + 1) / total)
            by_type.setdefault(problem_type, []).append(completion)
            reach = step_reach.setdefault(problem_type, [0] * total)
            for step in range(min(int(row["step_idx"]) + 1, total)):
                reach[step] += 1

        problem_types: list[dict[str, Any]] = []
        for problem_type in sorted(by_type):
            completions = by_type[problem_type]
            chains = len(completions)
            reached = step_reach.get(problem_type, [])
            problem_types.append(
                {
                    "problem_type": problem_type,
                    "chains": chains,
                    "avg_completion": sum(completions) / chains if chains else 0.0,
                    "step_retention": [
                        count / chains if chains else 0.0 for count in reached
                    ],
                }
            )
        return {"problem_types": problem_types}

    def dashboard_decay(
        self, *, tenant_id: str, horizon_days: int = 30
    ) -> dict[str, Any]:
        """Concept decay curves projected from ``last_practiced_at`` (R10.1.d)."""

        from .mastery import decay as decay_fn

        concepts = self.list_concepts(tenant_id=tenant_id)
        curves: list[dict[str, Any]] = []
        sample_days = [0, 1, 3, 7, 14, horizon_days]
        for concept in concepts:
            if not concept.last_practiced_at:
                continue
            lam = concept.decay_lambda or 0.05
            curves.append(
                {
                    "concept_id": concept.id,
                    "label": concept.label,
                    "mastery_score": concept.mastery_score,
                    "last_practiced_at": concept.last_practiced_at,
                    "decay_lambda": lam,
                    "projection": [
                        {
                            "day": day,
                            "score": decay_fn(concept.mastery_score, lam, float(day)),
                        }
                        for day in sample_days
                    ],
                }
            )
        return {"curves": curves, "horizon_days": horizon_days}

    def audit_log(self, *, tenant_id: str, limit: int = 40) -> list[dict[str, Any]]:
        with self._lock, self._connect() as db:
            rows = db.execute(
                "select * from audit_log where tenant_id = ? order by created_at desc limit ?",
                (tenant_id, limit),
            ).fetchall()
        return [
            {
                "id": row["id"],
                "actor": row["actor"],
                "action": row["action"],
                "subject": row["subject"],
                "payload_json": row["payload_json"],
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    # ---- internals ----------------------------------------------------

    def _hydrate_item(
        self,
        db: sqlite3.Connection,
        item_id: str,
        tenant_id: str,
        concept_ids: Optional[list[str]],
    ) -> KnowledgeItem:
        row = db.execute(
            "select * from knowledge_items where id = ? and tenant_id = ?",
            (item_id, tenant_id),
        ).fetchone()
        if row is None:
            raise KeyError(item_id)
        if concept_ids is None:
            concept_ids = _concepts_for_item(db, item_id)
        return _row_to_item(row, concept_ids)

    def _record_audit(
        self,
        *,
        tenant_id: str,
        actor: str,
        action: str,
        subject: str | None,
        payload: dict[str, Any] | None,
    ) -> str:
        with self._lock, self._connect() as db:
            audit_id = _log_audit(db, tenant_id, actor, action, subject, payload or {})
        return audit_id

    def _log_learning_signal(self, tenant_id: str, concept_id: str, event: str) -> None:
        with self._lock, self._connect() as db:
            db.execute(
                "insert into learning_signals(tenant_id, concept_id, event, created_at) values(?, ?, ?, ?)",
                (tenant_id, concept_id, event, _utc_now_iso()),
            )

    def _preference_snippets(self, tenant_id: str, limit: int) -> list[str]:
        with self._lock, self._connect() as db:
            rows = db.execute(
                """
                select text from memory_notes
                where tenant_id = ? and allow_into_knowledge_base = 1 and kind = 'preference'
                order by created_at desc
                limit ?
                """,
                (tenant_id, limit),
            ).fetchall()
        return [row["text"] for row in rows]


# ---------------------------------------------------------------------------
# helpers that do not need state
# ---------------------------------------------------------------------------


def clean_body(body: str) -> str:
    body = body.replace("\r\n", "\n").replace("\r", "\n")
    body = re.sub(r"\n{3,}", "\n\n", body)
    body = re.sub(r"[ \t]+", " ", body)
    body = re.sub(r"<script.*?</script>", "", body, flags=re.IGNORECASE | re.DOTALL)
    body = re.sub(r"<style.*?</style>", "", body, flags=re.IGNORECASE | re.DOTALL)
    body = re.sub(r"<[^>]+>", "", body)
    return body.strip()


def clean_title(title: str, body: str) -> str:
    title = re.sub(r"\s+", " ", title or "").strip()
    if not title:
        body_lines = [line for line in body.splitlines() if line.strip()]
        title = body_lines[0][:80] if body_lines else "Untitled"
    return title[:180]


def detect_language(text: str) -> str:
    cjk = sum(1 for ch in text if "\u4e00" <= ch <= "\u9fff")
    letters = sum(1 for ch in text if ch.isalpha())
    return "zh-CN" if cjk and (not letters or cjk * 2 >= letters) else "en"


def score_quality(
    *,
    body: str,
    source_kind: SourceKind,
    freshness_date: str | None,
    has_url: bool,
) -> dict[str, float]:
    """Transparent, reproducible quality score (0–1) and its components."""

    length_ratio = min(1.0, len(body) / 2400)
    paragraph_count = len([p for p in body.split("\n\n") if p.strip()])
    structure_ratio = min(1.0, paragraph_count / 6)

    # Accuracy (does it look well-formed, has it been through review).
    accuracy = 0.3 + 0.3 * length_ratio + 0.2 * structure_ratio
    if source_kind in {"direct_import", "enterprise_cleanse", "expert_search"}:
        accuracy += 0.1
    accuracy = min(1.0, accuracy)

    # Veracity (citations, url presence, kind bias toward trusted kinds).
    citation_density = len(re.findall(r"https?://", body)) / max(1, paragraph_count)
    veracity = 0.25 + 0.3 * min(1.0, citation_density) + (0.2 if has_url else 0.0)
    if source_kind in {"expert_search", "enterprise_cleanse"}:
        veracity += 0.2
    if source_kind in {"memory_note"}:
        veracity -= 0.1
    veracity = max(0.0, min(1.0, veracity))

    # Relevance (can't know for sure at absorption time, so reward
    # specificity via token diversity).
    tokens = [token for token in tokenize(body) if token not in STOPWORDS]
    unique_tokens = len(set(tokens))
    relevance = 0.25 + 0.5 * min(1.0, unique_tokens / 200) + 0.2 * structure_ratio
    relevance = max(0.0, min(1.0, relevance))

    # Freshness bonus (up to +0.1) if a recent freshness_date was supplied.
    freshness = 0.0
    if freshness_date:
        try:
            dt = datetime.fromisoformat(freshness_date.replace("Z", "+00:00"))
            age_days = max(0.0, (datetime.now(timezone.utc) - dt).days)
            freshness = max(0.0, 0.1 - min(age_days, 365) / 365 * 0.1)
        except Exception:
            freshness = 0.0

    quality = max(0.0, min(1.0, 0.45 * accuracy + 0.35 * veracity + 0.2 * relevance + freshness))
    return {
        "quality_score": quality,
        "accuracy_score": accuracy,
        "veracity_score": veracity,
        "relevance_score": relevance,
    }


def classify_tier(score: float) -> QualityTier:
    if score >= 0.75:
        return "verified"
    if score >= 0.55:
        return "needs_review"
    if score >= 0.3:
        return "insufficient"
    return "rejected"


def memory_filter(text: str) -> tuple[bool, str]:
    lowered = text.lower()
    for marker in ("password", "passwd", "secret", "api key", "apikey", "token ", "私密", "密码"):
        if marker in lowered:
            return False, f"contains sensitive marker: {marker}"
    if len(text) > 2000:
        return False, "memory note too long (>2000 chars)"
    if len(text) < 4:
        return False, "memory note too short"
    return True, "passed deterministic filter"


def derive_knowledge_gaps(question: str) -> list[str]:
    tokens = [t for t in tokenize(question) if t not in STOPWORDS and len(t) > 1]
    keys = list(dict.fromkeys(tokens))[:5]
    return keys


def suggested_next_actions(question: str, language: str) -> list[str]:
    if language == "zh-CN":
        return [
            "用浏览器扩展把最能回答此问题的 2–3 个权威页面存入知识库。",
            "在知识库里搜索相近概念，手动关联到当前问题。",
            "打开设置运行一次模型智力测试，确保当前模型足以回答此问题。",
        ]
    return [
        "Save two or three authoritative pages answering this into your library.",
        "Search the library for nearby concepts and link them manually.",
        "Run the model intelligence test to confirm the current model is strong enough.",
    ]


def _prompt_strategy_for_tier(tier: str) -> str:
    return {
        "flagship": "single_stage_instruction",
        "mid": "two_stage_clarify_then_answer",
        "basic": "multi_stage_decompose_verify",
        "insufficient": "not_recommended",
    }.get(tier, "single_stage_instruction")


def _rewrite_prompt(
    prompt: str,
    thinking: dict[str, Any],
    memory_lines: list[str],
    language: str,
) -> str:
    if language == "zh-CN":
        sections = [
            f"【思维模型】{thinking['label_zh']}",
            "【角色】你是我请来的世界顶级专家，答案要准确、可溯源。",
            "【任务】" + prompt,
        ]
        if memory_lines:
            sections.append("【我的偏好】\n- " + "\n- ".join(memory_lines))
        sections.append("【要求】先列出关键前提与潜在误区，再给出行动化结论，最后标注置信带（高/中/低）和未知项。")
        return "\n\n".join(sections)
    sections = [
        f"[thinking model] {thinking['label_en']}",
        "[role] you are a top expert; answers must be accurate and source-traceable.",
        "[task] " + prompt,
    ]
    if memory_lines:
        sections.append("[my preferences]\n- " + "\n- ".join(memory_lines))
    sections.append("[format] state assumptions and pitfalls, give an actionable answer, then mark confidence (high/medium/low) and unknowns.")
    return "\n\n".join(sections)


def _compose_answer(
    *,
    question: str,
    thinking: dict[str, Any],
    language: str,
    citations: list[AnswerCitation],
    confidence_band: str,
    gaps: list[str],
) -> str:
    if confidence_band == "insufficient":
        if language == "zh-CN":
            if gaps:
                gaps_str = "、".join(gaps)
                return f"当前知识库中关于「{gaps_str}」的证据不足以给出可靠答案。请先通过扩展或直接导入相关权威资料，再来询问。"
            return "当前知识库证据不足以给出可靠答案；请先补充相关权威资料。"
        if gaps:
            return f"Insufficient evidence in your knowledge base about {', '.join(gaps)}. Capture authoritative material before asking again."
        return "Insufficient evidence in your knowledge base to answer reliably. Please capture authoritative material first."

    bullets: list[str] = []
    for citation in citations[:3]:
        bullets.append(f"- {citation.snippet}  [[{citation.item_id}]]")
    bullets_str = "\n".join(bullets) if bullets else ""

    if language == "zh-CN":
        header = f"按「{thinking['label_zh']}」分析问题：{question}\n\n结合已知证据，要点如下："
        trailer = (
            "\n\n置信：" + {"solid": "高", "probable": "中", "uncertain": "低"}[confidence_band]
            + "。如需更高确定性，请补充权威来源或在监督模式下再走一遍验证。"
        )
    else:
        header = f"Using the {thinking['label_en']} lens on: {question}\n\nKey points grounded in your evidence:"
        trailer = (
            "\n\nConfidence: "
            + {"solid": "high", "probable": "medium", "uncertain": "low"}[confidence_band]
            + ". For higher certainty add authoritative sources or verify in supervised mode."
        )
    return header + ("\n" + bullets_str if bullets_str else "") + trailer


def _compose_draft_answer(
    *,
    question: str,
    thinking: dict[str, Any],
    language: str,
    citations: list[AnswerCitation],
    confidence_band: str,
    gaps: list[str],
) -> str:
    """Like _compose_answer but marks subjective claims with [?]."""
    base = _compose_answer(
        question=question,
        thinking=thinking,
        language=language,
        citations=citations,
        confidence_band=confidence_band,
        gaps=gaps,
    )
    if not base:
        return base
    # Mark lines without citation markers as subjective
    lines = base.split("\n")
    marked: list[str] = []
    for line in lines:
        if line.strip().startswith("-") and "[[" not in line:
            marked.append(line + " [?]")
        else:
            marked.append(line)
    draft_label = "【草稿，需人工审查】" if language == "zh-CN" else "[DRAFT — requires human review]"
    return draft_label + "\n" + "\n".join(marked)


def _derive_candidate_angles(question: str, thinking: dict[str, Any], language: str) -> list[str]:
    """Generate 3 candidate analysis angles from different thinking models."""
    # Pick 3 models: the selected one + 2 others
    selected_id = thinking["id"]
    others = [m for m in THINKING_MODELS if m["id"] != selected_id][:2]
    models_to_use = [thinking] + others

    angles: list[str] = []
    for model in models_to_use:
        label = model["label_zh"] if language == "zh-CN" else model["label_en"]
        if language == "zh-CN":
            angles.append(f"用「{label}」视角：从这个框架出发，关键问题是什么？")
        else:
            angles.append(f"Through the '{label}' lens: what is the key question from this framework?")
    return angles


def _derive_open_questions(question: str, citations: list[AnswerCitation], language: str) -> list[str]:
    """Generate open questions the user should answer themselves (not outsource to Agent)."""
    if language == "zh-CN":
        base = [
            "你对这个问题的成功标准是什么？（Agent 不能替你定义）",
            "你愿意为此投入的最大资源是什么？",
            "如果这个方向失败了，你的止损点在哪里？",
            "你目前掌握的最强证据是什么？",
            "有哪些你已知的约束条件？",
        ]
    else:
        base = [
            "What does success look like for you? (Agent cannot define this for you)",
            "What is the maximum resource you are willing to invest?",
            "If this direction fails, what is your stop-loss point?",
            "What is the strongest evidence you currently hold?",
            "What constraints do you already know about?",
        ]
    # If we have citations, add a citation-specific question
    if citations and language == "zh-CN":
        base.append(f"知识库中找到 {len(citations)} 条相关证据，你认为哪些是可信的？")
    elif citations:
        base.append(f"Found {len(citations)} relevant citations — which do you consider trustworthy?")
    return base[:5]


def _derive_key_tradeoffs(question: str, language: str) -> list[str]:
    """Surface 2-3 key tradeoffs the user must decide on."""
    if language == "zh-CN":
        return [
            "速度 vs 质量：快速验证还是深度研究？",
            "广度 vs 深度：覆盖更多方向还是聚焦一个？",
            "自建 vs 外包：哪些环节必须自己做？",
        ]
    return [
        "Speed vs quality: quick validation or deep research?",
        "Breadth vs depth: cover more directions or focus on one?",
        "Build vs buy: which parts must you do yourself?",
    ]


def _run_acceptance_check(
    *,
    answer: str,
    citations: list[AnswerCitation],
    confidence_band: str,
    task_contract: dict[str, Any] | None,
    language: str,
    run_id: str | None = None,
) -> dict[str, Any]:
    """Dual acceptance check (L4 verification layer).

    Check 1 (truthfulness): Are citations grounded? Do we have enough evidence?
    Check 2 (goal_fit): Does the answer address the task_contract goals?

    Step 4: When REALITY_OS_VERIFIER_URL is set, an independent verifier model
    (separate from the generator) performs a second-pass review. The verifier
    must be a DIFFERENT model/provider from the one that generated the answer
    to avoid self-confirmation bias. Falls back to deterministic checks when
    the verifier is not configured.
    """
    # --- Deterministic truthfulness check ---
    citation_count = len(citations)
    high_quality_citations = sum(1 for c in citations if c.quality >= 0.6)
    truthfulness_passed = confidence_band in ("solid", "probable") and high_quality_citations >= 1
    failed_citations = [c.item_id for c in citations if c.quality < 0.4]

    if truthfulness_passed:
        truth_reason = "Sufficient high-quality citations support the answer."
    elif confidence_band == "insufficient":
        truth_reason = "Insufficient evidence in knowledge base."
    else:
        truth_reason = f"Low citation quality: {len(failed_citations)} citation(s) below threshold."

    # --- Deterministic goal fit check ---
    goal_fit_passed = True
    unmet_criteria: list[str] = []
    if task_contract:
        acceptance_criteria = task_contract.get("acceptance_criteria", [])
        goal = task_contract.get("goal", "")
        # Simple heuristic: check if the answer mentions key terms from the goal
        if goal and answer:
            goal_tokens = {t for t in tokenize(goal) if t not in STOPWORDS and len(t) > 1}
            answer_tokens = set(tokenize(answer))
            coverage = len(goal_tokens & answer_tokens) / max(1, len(goal_tokens))
            if coverage < 0.3:
                goal_fit_passed = False
                unmet_criteria.append(
                    "答案未充分覆盖任务目标的关键词" if language == "zh-CN"
                    else "Answer does not sufficiently address the task goal keywords"
                )
        for criterion in acceptance_criteria:
            criterion_tokens = {t for t in tokenize(str(criterion)) if t not in STOPWORDS and len(t) > 1}
            if criterion_tokens and not (criterion_tokens & set(tokenize(answer))):
                goal_fit_passed = False
                unmet_criteria.append(str(criterion))
    else:
        # No task_contract: goal_fit is trivially passed (backward compat)
        goal_fit_passed = True

    # --- Step 4: LLM verifier pass (optional, independent model) ---
    verifier_result = _try_llm_verifier(
        answer=answer,
        citations=citations,
        task_contract=task_contract,
        language=language,
        run_id=run_id,
    )

    # Merge verifier result if available (verifier can only DOWNGRADE, never upgrade)
    verifier_used = verifier_result is not None
    if verifier_result:
        if not verifier_result.get("truthfulness_ok", True):
            truthfulness_passed = False
            truth_reason = verifier_result.get("truthfulness_reason", truth_reason)
        if not verifier_result.get("goal_fit_ok", True):
            goal_fit_passed = False
            extra_unmet = verifier_result.get("unmet_criteria", [])
            unmet_criteria.extend(extra_unmet)

    # --- Verdict ---
    if truthfulness_passed and goal_fit_passed:
        verdict = "accepted"
    elif not truthfulness_passed:
        verdict = "needs_revision"
    else:
        verdict = "needs_revision"

    return {
        "truthfulness": {
            "passed": truthfulness_passed,
            "reason": truth_reason,
            "failed_citations": failed_citations,
        },
        "goal_fit": {
            "passed": goal_fit_passed,
            "reason": "All criteria met." if goal_fit_passed else "Some acceptance criteria unmet.",
            "unmet_criteria": unmet_criteria,
        },
        "verdict": verdict,
        "verifier_used": verifier_used,
    }


def _try_llm_verifier(
    *,
    answer: str,
    citations: list[AnswerCitation],
    task_contract: dict[str, Any] | None,
    language: str,
    run_id: str | None = None,
) -> dict[str, Any] | None:
    """Attempt to call an independent verifier model for L4 acceptance.

    Step 4: Uses the Model Registry's "verifier" slot. If not configured,
    falls back to checking environment variables for backward compatibility.
    Returns None if no verifier is available (graceful degradation).
    The verifier can only DOWNGRADE acceptance (flag issues), never upgrade.
    """
    import os

    # Try Model Registry first (preferred path — configured via /settings UI)
    try:
        from .model_registry import call_model as _call_model
        verifier_available = True
    except Exception:
        verifier_available = False
        _call_model = None  # type: ignore[assignment]

    if not answer:
        return None  # Nothing to verify (scaffold mode)

    # Build the verification prompt
    citation_summary = "\n".join(
        f"- [{c.item_id}] {c.title}: {c.snippet[:100]}" for c in citations[:4]
    )
    goal_section = ""
    if task_contract:
        goal_section = f"\nTask goal: {task_contract.get('goal', 'not specified')}"
        criteria = task_contract.get("acceptance_criteria", [])
        if criteria:
            goal_section += f"\nAcceptance criteria: {', '.join(str(c) for c in criteria)}"

    prompt = (
        "You are an independent verification agent. Your job is to check an AI-generated answer "
        "for truthfulness and goal fitness. You must be STRICT — flag any issue.\n\n"
        f"ANSWER TO VERIFY:\n{answer[:1500]}\n\n"
        f"CITATIONS PROVIDED:\n{citation_summary}\n"
        f"{goal_section}\n\n"
        "Respond in JSON only:\n"
        '{"truthfulness_ok": true/false, "truthfulness_reason": "...", '
        '"goal_fit_ok": true/false, "unmet_criteria": ["..."]}\n'
        "Be strict. If the answer makes claims not supported by the citations, set truthfulness_ok=false."
    )

    # Path 1: Use Model Registry (configured via frontend /settings)
    if verifier_available and _call_model:
        result_text = _call_model(
            "verifier",
            prompt=prompt,
            temperature=0.0,
            max_tokens=300,
            timeout=10,
            run_id=run_id,
        )
        if result_text:
            return _parse_verifier_response(result_text)

    # Path 2: Fallback to environment variables (backward compat)
    verifier_url = os.environ.get("REALITY_OS_VERIFIER_URL", "").strip()
    verifier_key = os.environ.get("REALITY_OS_VERIFIER_KEY", "").strip()
    verifier_model = os.environ.get("REALITY_OS_VERIFIER_MODEL", "").strip()

    if not verifier_url or not verifier_key or not verifier_model:
        return None  # No verifier configured at all

    try:
        import urllib.request
        import json as _json

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {verifier_key}",
        }
        payload = _json.dumps({
            "model": verifier_model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.0,
            "max_tokens": 300,
        }).encode("utf-8")

        req = urllib.request.Request(
            f"{verifier_url.rstrip('/')}/chat/completions",
            data=payload,
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = _json.loads(resp.read().decode("utf-8"))

        content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
        return _parse_verifier_response(content)
    except Exception:
        return None


def _parse_verifier_response(content: str) -> dict[str, Any] | None:
    """Parse the JSON response from the verifier model."""
    import json as _json

    content = content.strip()
    if content.startswith("```"):
        content = "\n".join(content.split("\n")[1:])
    if content.endswith("```"):
        content = content[: content.rfind("```")]
    content = content.strip()

    try:
        parsed = _json.loads(content)
        return {
            "truthfulness_ok": bool(parsed.get("truthfulness_ok", True)),
            "truthfulness_reason": str(parsed.get("truthfulness_reason", "")),
            "goal_fit_ok": bool(parsed.get("goal_fit_ok", True)),
            "unmet_criteria": list(parsed.get("unmet_criteria", [])),
        }
    except Exception:
        return None


def _aggregate_confidence(citations: list[AnswerCitation]) -> float:
    if not citations:
        return 0.0
    weights = [0.6 * citation.relevance + 0.4 * citation.quality for citation in citations]
    avg = sum(weights) / len(weights)
    depth_bonus = min(0.1, len(citations) * 0.02)
    return max(0.0, min(1.0, avg + depth_bonus))


def _derive_snippet(body: str, question: str, length: int = 220) -> str:
    query_tokens = {token for token in tokenize(question) if len(token) > 1}
    best_index = 0
    best_score = -1
    step = 40
    for index in range(0, max(1, len(body) - length + 1), step):
        window = body[index : index + length]
        score = sum(1 for token in tokenize(window) if token in query_tokens)
        if score > best_score:
            best_score = score
            best_index = index
    snippet = body[best_index : best_index + length].strip()
    if best_index > 0:
        snippet = "…" + snippet
    if best_index + length < len(body):
        snippet = snippet + "…"
    return snippet


def _json_tags(tags: Iterable[str]) -> str:
    import json

    cleaned = [str(tag).strip() for tag in tags if str(tag).strip()]
    return json.dumps(cleaned, ensure_ascii=False)


def _parse_tags(raw: str) -> list[str]:
    import json

    try:
        value = json.loads(raw or "[]")
    except Exception:
        return []
    return [str(item) for item in value if isinstance(item, (str, int, float))]


def _log_audit(
    db: sqlite3.Connection,
    tenant_id: str,
    actor: str,
    action: str,
    subject: str | None,
    payload: dict[str, Any],
) -> str:
    import json

    audit_id = _new_id("aud")
    db.execute(
        "insert into audit_log(id, tenant_id, actor, action, subject, payload_json, created_at) values(?, ?, ?, ?, ?, ?, ?)",
        (audit_id, tenant_id, actor, action, subject, json.dumps(payload, ensure_ascii=False), _utc_now_iso()),
    )
    return audit_id


def _canonicalize_url(url: str | None) -> str | None:
    if not url:
        return None
    try:
        parsed = urlsplit(url.strip())
    except ValueError:
        return url.strip()[:500] or None
    if not parsed.scheme or not parsed.netloc:
        return url.strip()[:500] or None
    return urlunsplit(
        (
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            parsed.path or "",
            parsed.query or "",
            "",
        )
    )[:500]


def _source_publisher(source_url: str | None) -> str | None:
    canonical = _canonicalize_url(source_url)
    if not canonical:
        return None
    try:
        return urlsplit(canonical).netloc or None
    except ValueError:
        return None


def _safe_excerpt(text: str, limit: int = 600) -> str:
    cleaned = _redact_sensitive_text(clean_body(text))
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[:limit].rsplit(" ", 1)[0].strip() or cleaned[:limit].strip()


def _surrounding_context(text: str, excerpt: str, limit: int = 900) -> str:
    if not text or not excerpt:
        return ""
    redacted_text = _redact_sensitive_text(text)
    idx = redacted_text.find(excerpt[:80])
    if idx < 0:
        return _safe_excerpt(redacted_text, limit)
    start = max(0, idx - 160)
    end = min(len(redacted_text), idx + len(excerpt) + 160)
    return redacted_text[start:end].strip()[:limit]


def _redact_sensitive_text(text: str) -> str:
    redacted = re.sub(r"\bsk-[A-Za-z0-9_-]{8,}\b", "[redacted-secret]", text)
    redacted = re.sub(
        r"(?i)\b(api[_\s-]?key|token|secret|password)\s*[:=]\s*['\"]?[^'\"\s,;]{6,}",
        r"\1=[redacted-secret]",
        redacted,
    )
    redacted = re.sub(
        r"(?i)\b(api[_\s-]?key|token|secret|password)\s+is\s+[^.\n,;]{6,}",
        r"\1 is [redacted-secret]",
        redacted,
    )
    return redacted


def _json_metadata(metadata: dict[str, Any] | None) -> str:
    import json

    safe: dict[str, Any] = {}
    for key, value in (metadata or {}).items():
        key_text = str(key)
        lowered = key_text.lower()
        if any(token in lowered for token in ("api_key", "apikey", "token", "secret", "password", "authorization", "prompt", "input", "content")):
            safe[key_text] = "[redacted]"
        elif isinstance(value, (str, int, float, bool)) or value is None:
            safe[key_text] = value
        else:
            safe[key_text] = str(value)[:200]
    return json.dumps(safe, ensure_ascii=False, sort_keys=True, default=str)


def _create_evidence_snapshot_row(
    db: sqlite3.Connection,
    *,
    tenant_id: str,
    title: str,
    content: str,
    source_kind: str,
    source_url: str | None,
    canonical_url: str | None = None,
    publisher: str | None = None,
    author: str | None = None,
    published_at: str | None = None,
    credibility_score: float = 0.0,
    retrieval_score: float | None = None,
    item_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> EvidenceSnapshot:
    content_clean = clean_body(content)
    excerpt = _safe_excerpt(content_clean)
    context = _surrounding_context(content_clean, excerpt)
    snapshot = EvidenceSnapshot(
        snapshot_id=_new_id("snap"),
        tenant_id=tenant_id,
        source_url=source_url,
        canonical_url=canonical_url or _canonicalize_url(source_url),
        title=clean_title(title, content_clean),
        publisher=publisher or _source_publisher(source_url),
        author=author,
        published_at=published_at,
        fetched_at=_utc_now_iso(),
        content_hash=_content_hash(content_clean),
        excerpt=excerpt,
        excerpt_hash=_content_hash(excerpt),
        surrounding_context=context,
        credibility_score=max(0.0, min(1.0, float(credibility_score or 0.0))),
        retrieval_score=max(0.0, min(1.0, float(retrieval_score))) if retrieval_score is not None else None,
        source_kind=str(source_kind),
        item_id=item_id,
        security_flags=flags_for_text(content_clean, source=f"evidence_snapshot:{source_kind}"),
        content_role="evidence",
    )
    db.execute(
        """
        insert into evidence_snapshots(
          snapshot_id, tenant_id, source_url, canonical_url, title, publisher,
          author, published_at, fetched_at, content_hash, excerpt, excerpt_hash,
          surrounding_context, credibility_score, retrieval_score, source_kind,
          item_id, security_flags_json, content_role, metadata_json
        ) values(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            snapshot.snapshot_id,
            snapshot.tenant_id,
            snapshot.source_url,
            snapshot.canonical_url,
            snapshot.title,
            snapshot.publisher,
            snapshot.author,
            snapshot.published_at,
            snapshot.fetched_at,
            snapshot.content_hash,
            snapshot.excerpt,
            snapshot.excerpt_hash,
            snapshot.surrounding_context,
            snapshot.credibility_score,
            snapshot.retrieval_score,
            snapshot.source_kind,
            snapshot.item_id,
            _json_tags(snapshot.security_flags),
            snapshot.content_role,
            _json_metadata(metadata),
        ),
    )
    return snapshot


def _load_evidence_snapshot(
    db: sqlite3.Connection,
    tenant_id: str,
    snapshot_id: str | None,
) -> EvidenceSnapshot | None:
    if not snapshot_id:
        return None
    row = db.execute(
        "select * from evidence_snapshots where tenant_id = ? and snapshot_id = ?",
        (tenant_id, snapshot_id),
    ).fetchone()
    if row is None:
        return None
    return EvidenceSnapshot(
        snapshot_id=row["snapshot_id"],
        tenant_id=row["tenant_id"],
        source_url=row["source_url"],
        canonical_url=row["canonical_url"],
        title=row["title"],
        publisher=row["publisher"],
        author=row["author"],
        published_at=row["published_at"],
        fetched_at=row["fetched_at"],
        content_hash=row["content_hash"],
        excerpt=row["excerpt"],
        excerpt_hash=row["excerpt_hash"],
        surrounding_context=row["surrounding_context"],
        credibility_score=float(row["credibility_score"]),
        retrieval_score=float(row["retrieval_score"]) if row["retrieval_score"] is not None else None,
        source_kind=row["source_kind"],
        item_id=row["item_id"],
        security_flags=_parse_tags(row["security_flags_json"]),
        content_role=row["content_role"],
    )


def _row_to_item(row: sqlite3.Row, concept_ids: list[str]) -> KnowledgeItem:
    return KnowledgeItem(
        id=row["id"],
        title=row["title"],
        body=row["body"],
        source_kind=row["source_kind"],  # type: ignore[arg-type]
        source_url=row["source_url"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        content_hash=row["content_hash"],
        quality_score=float(row["quality_score"]),
        quality_tier=row["quality_tier"],  # type: ignore[arg-type]
        tags=_parse_tags(row["tags_json"]),
        language=row["language"],
        tenant_id=row["tenant_id"],
        review_required=bool(row["review_required"]),
        freshness_date=row["freshness_date"],
        accuracy_score=float(row["accuracy_score"]),
        veracity_score=float(row["veracity_score"]),
        relevance_score=float(row["relevance_score"]),
        concept_ids=concept_ids,
        applicability_scope=row["applicability_scope"] if "applicability_scope" in row.keys() else None,
        conflict_state=row["conflict_state"] if "conflict_state" in row.keys() else "none",  # type: ignore[arg-type]
        conflicts_with=_parse_tags(row["conflicts_with_json"]) if "conflicts_with_json" in row.keys() else [],
        security_flags=_parse_tags(row["security_flags_json"]) if "security_flags_json" in row.keys() else [],
        snapshot_id=row["snapshot_id"] if "snapshot_id" in row.keys() else None,
        excerpt_hash=row["excerpt_hash"] if "excerpt_hash" in row.keys() else None,
        model_summary_id=row["model_summary_id"] if "model_summary_id" in row.keys() else None,
        needs_refresh=bool(row["needs_refresh"]) if "needs_refresh" in row.keys() else False,
        validation_status=row["validation_status"] if "validation_status" in row.keys() else "not_validated",  # type: ignore[arg-type]
    )


def _derive_applicability_scope(body: str, source_kind: SourceKind) -> str | None:
    """Deterministically derive a brief applicability scope from the content.

    Looks for explicit boundary markers in the text. If none found, returns
    a generic scope based on source_kind. Users can override this later.
    """
    # Look for explicit scope markers
    _SCOPE_MARKERS_ZH = ("适用于", "仅限", "前提是", "条件是", "在…情况下", "当…时")
    _SCOPE_MARKERS_EN = ("applies to", "only for", "assuming", "given that", "when ", "limited to", "in the context of")

    body_lower = body.lower()
    for marker in _SCOPE_MARKERS_ZH:
        idx = body_lower.find(marker)
        if idx >= 0:
            # Extract up to 120 chars after the marker
            snippet = body[idx:idx + 120].split("\n")[0].strip()
            return snippet if snippet else None
    for marker in _SCOPE_MARKERS_EN:
        idx = body_lower.find(marker)
        if idx >= 0:
            snippet = body[idx:idx + 120].split("\n")[0].strip()
            return snippet if snippet else None

    # Fallback: generic scope by source kind
    _KIND_SCOPE = {
        "browser_capture": "web content; verify freshness before relying on it",
        "ai_answer_capture": "AI-generated; treat as hypothesis until verified",
        "memory_note": "personal note; context-dependent",
        "expert_search": "expert-sourced; generally reliable within stated domain",
    }
    return _KIND_SCOPE.get(source_kind)


def _detect_conflicts(
    db: sqlite3.Connection,
    tenant_id: str,
    item_id: str,
    concept_ids: list[str],
    body: str,
) -> list[str]:
    """Detect potential conflicts with existing items sharing concepts.

    Uses a simple heuristic: if another item shares concepts but contains
    opposing signal words (negation patterns), flag it as a potential conflict.
    This is deterministic and does not require an LLM.
    """
    if not concept_ids:
        return []

    # Find other items sharing the same concepts
    placeholders = ",".join("?" for _ in concept_ids)
    rows = db.execute(
        f"""
        select distinct ci.item_id
        from concept_item ci
        join knowledge_items ki on ki.id = ci.item_id
        where ci.concept_id in ({placeholders})
          and ci.item_id != ?
          and ki.tenant_id = ?
          and ki.quality_tier != 'rejected'
        limit 20
        """,
        [*concept_ids, item_id, tenant_id],
    ).fetchall()

    if not rows:
        return []

    # Simple opposition detection: check if the new body contains negation
    # patterns relative to shared-concept siblings.
    _NEGATION_ZH = {"不是", "并非", "错误", "过时", "已废弃", "不再", "相反", "反对"}
    _NEGATION_EN = {"not", "incorrect", "wrong", "outdated", "deprecated", "contrary", "false", "disagree"}
    negations = _NEGATION_ZH | _NEGATION_EN

    body_lower = body.lower()
    has_negation = any(neg in body_lower for neg in negations)
    if not has_negation:
        return []

    # Only flag items whose body also has negation or whose content overlaps
    # significantly (shared tokens > 30%).
    new_tokens = set(tokenize(body))
    conflicts: list[str] = []
    for row in rows:
        other_id = row["item_id"]
        other_row = db.execute(
            "select body from knowledge_items where id = ?", (other_id,)
        ).fetchone()
        if other_row is None:
            continue
        other_tokens = set(tokenize(other_row["body"]))
        overlap = len(new_tokens & other_tokens) / max(1, min(len(new_tokens), len(other_tokens)))
        if overlap > 0.3:
            conflicts.append(other_id)
            if len(conflicts) >= 3:
                break

    return conflicts


def _index_tokens(db: sqlite3.Connection, item_id: str, text: str) -> None:
    tokens = [token for token in tokenize(text) if token not in STOPWORDS and len(token) > 1]
    if not tokens:
        return
    counts: dict[str, int] = {}
    for token in tokens:
        counts[token] = counts.get(token, 0) + 1
    total = sum(counts.values())
    db.execute("delete from item_tokens where item_id = ?", (item_id,))
    db.executemany(
        "insert into item_tokens(item_id, token, weight) values(?, ?, ?)",
        [(item_id, token, count / total) for token, count in counts.items()],
    )


def _minmax_norm(value: float, lo: float, hi: float) -> float:
    """Min-max normalise ``value`` into ``[0, 1]`` (hybrid retrieval, R8.2).

    A degenerate range (``hi == lo``) maps every value to ``0.0`` so a
    single-candidate result set does not get an artificial full score.
    """

    if hi <= lo:
        return 0.0
    return max(0.0, min(1.0, (value - lo) / (hi - lo)))


def _fts_search(db: sqlite3.Connection, tenant_id: str, query: str, limit: int) -> list[tuple[str, float]]:
    tokens = [token for token in tokenize(query) if token not in STOPWORDS and len(token) > 1]
    if not tokens:
        return []
    match_expr = " OR ".join(f'"{token.replace(chr(34), "")}"' for token in tokens[:12])
    try:
        rows = db.execute(
            """
            select knowledge_items.id as id, bm25(knowledge_items_fts) as score
            from knowledge_items_fts
            join knowledge_items on knowledge_items.rowid = knowledge_items_fts.rowid
            where knowledge_items_fts match ? and knowledge_items.tenant_id = ?
            order by score asc
            limit ?
            """,
            (match_expr, tenant_id, limit),
        ).fetchall()
    except sqlite3.OperationalError:
        return []
    results: list[tuple[str, float]] = []
    for row in rows:
        # BM25 returns lower = better; normalise to 0..1 roughly.
        raw = row["score"]
        score = 1.0 / (1.0 + max(0.0, raw))
        results.append((row["id"], score))
    return results


def _tfidf_search(db: sqlite3.Connection, tenant_id: str, query: str, limit: int) -> list[tuple[str, float]]:
    query_tokens = [token for token in tokenize(query) if token not in STOPWORDS and len(token) > 1]
    if not query_tokens:
        return []
    rows = db.execute(
        """
        select token, count(distinct item_id) as df
        from item_tokens
        where token in ({placeholders})
        group by token
        """.format(placeholders=",".join("?" for _ in query_tokens)),
        query_tokens,
    ).fetchall()
    df_map = {row["token"]: int(row["df"]) for row in rows}
    total_items = db.execute(
        "select count(*) as count from knowledge_items where tenant_id = ?",
        (tenant_id,),
    ).fetchone()["count"]
    if total_items == 0 or not df_map:
        return []

    query_weights: dict[str, float] = {}
    for token in query_tokens:
        df = df_map.get(token, 0)
        if df == 0:
            continue
        idf = math.log((total_items + 1) / (df + 0.5))
        query_weights[token] = idf
    if not query_weights:
        return []

    placeholders = ",".join("?" for _ in query_weights)
    item_rows = db.execute(
        """
        select item_tokens.item_id as item_id, item_tokens.token as token, item_tokens.weight as weight
        from item_tokens
        join knowledge_items on knowledge_items.id = item_tokens.item_id
        where knowledge_items.tenant_id = ? and item_tokens.token in ({placeholders})
        """.format(placeholders=placeholders),
        [tenant_id, *query_weights.keys()],
    ).fetchall()

    per_item: dict[str, float] = {}
    for row in item_rows:
        weight = float(row["weight"]) * query_weights[row["token"]]
        per_item[row["item_id"]] = per_item.get(row["item_id"], 0.0) + weight

    # Normalise by rough doc magnitude.
    if not per_item:
        return []
    max_score = max(per_item.values())
    results = [(item_id, score / max_score) for item_id, score in per_item.items()]
    results.sort(key=lambda entry: entry[1], reverse=True)
    return results[:limit]


def _attach_concepts(
    db: sqlite3.Connection,
    tenant_id: str,
    item_id: str,
    title: str,
    body: str,
    now: str,
) -> list[str]:
    labels = derive_concept_labels(title, body)
    concept_ids: list[str] = []
    for label in labels:
        row = db.execute(
            "select id from concepts where tenant_id = ? and label = ?",
            (tenant_id, label),
        ).fetchone()
        if row is None:
            concept_id = _new_id("cpt")
            db.execute(
                "insert into concepts(id, tenant_id, label, summary, created_at) values(?, ?, ?, ?, ?)",
                (concept_id, tenant_id, label, body[:240], now),
            )
        else:
            concept_id = row["id"]
        db.execute(
            "insert or ignore into concept_item(concept_id, item_id) values(?, ?)",
            (concept_id, item_id),
        )
        concept_ids.append(concept_id)

    for i, a in enumerate(concept_ids):
        for b in concept_ids[i + 1 :]:
            db.execute(
                """
                insert into concept_edges(a, b, weight) values(?, ?, 1.0)
                on conflict(a, b) do update set weight = weight + 0.5
                """,
                (a, b),
            )
            db.execute(
                """
                insert into concept_edges(a, b, weight) values(?, ?, 1.0)
                on conflict(a, b) do update set weight = weight + 0.5
                """,
                (b, a),
            )
    return concept_ids


def derive_concept_labels(title: str, body: str) -> list[str]:
    tokens = [token for token in tokenize(f"{title} {body}") if token not in STOPWORDS and len(token) > 1]
    freq: dict[str, int] = {}
    for token in tokens:
        freq[token] = freq.get(token, 0) + 1
    ranked = sorted(freq.items(), key=lambda entry: entry[1], reverse=True)
    labels: list[str] = []
    for token, _count in ranked:
        if len(labels) >= 5:
            break
        labels.append(token)
    if not labels:
        labels.append(title[:20] or "unlabeled")
    return labels


def _concepts_for_item(db: sqlite3.Connection, item_id: str) -> list[str]:
    return [row["concept_id"] for row in db.execute(
        "select concept_id from concept_item where item_id = ?",
        (item_id,),
    ).fetchall()]


def _concept_mastery_kwargs(row: sqlite3.Row) -> dict[str, Any]:
    """Extract SM-2 mastery fields from a ``concepts`` row with safe fallbacks.

    Older rows persisted before the additive migration (Task 1.2) may not
    expose these columns at all. Newer rows have NOT NULL defaults for the
    numeric fields and may carry NULL for the optional timestamp/domain
    columns. Either way we fall back to the dataclass defaults so the
    Concept always constructs cleanly (R5.1, R5.6).
    """

    keys = set(row.keys())
    kwargs: dict[str, Any] = {}

    if "mastery_score" in keys and row["mastery_score"] is not None:
        kwargs["mastery_score"] = float(row["mastery_score"])
    if "last_practiced_at" in keys:
        kwargs["last_practiced_at"] = row["last_practiced_at"]
    if "next_due_at" in keys:
        kwargs["next_due_at"] = row["next_due_at"]
    if "decay_lambda" in keys and row["decay_lambda"] is not None:
        kwargs["decay_lambda"] = float(row["decay_lambda"])
    if "ef" in keys and row["ef"] is not None:
        kwargs["ef"] = float(row["ef"])
    if "repetition" in keys and row["repetition"] is not None:
        kwargs["repetition"] = int(row["repetition"])
    if "interval_days" in keys and row["interval_days"] is not None:
        kwargs["interval_days"] = float(row["interval_days"])
    if "domain" in keys:
        kwargs["domain"] = row["domain"]

    return kwargs


def _parse_iso(value: str) -> datetime:
    """Parse an ISO-8601 timestamp into an aware UTC :class:`datetime`.

    Accepts the ``Z`` suffix that ``datetime.isoformat`` does not emit but
    that some external sources do. Naive timestamps are assumed to be UTC.
    """

    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _topological_order(
    node_ids: set[str],
    adjacency: dict[str, list[str]],
    indegree: dict[str, int],
    row_by_id: dict[str, sqlite3.Row],
) -> list[str]:
    """Return ``node_ids`` ordered so prereqs precede dependents.

    Uses Kahn's algorithm with a deterministic tiebreaker (``created_at``,
    then ``id``) so callers see a stable order. Cycles are tolerated:
    once the queue drains, any remaining nodes are appended in the same
    deterministic order so a malformed prerequisite graph never silently
    drops concepts.
    """

    def _sort_key(concept_id: str) -> tuple[str, str]:
        row = row_by_id[concept_id]
        return (row["created_at"] or "", concept_id)

    queue = sorted(
        [cid for cid in node_ids if indegree.get(cid, 0) == 0],
        key=_sort_key,
    )
    indegree = dict(indegree)
    ordered: list[str] = []
    visited: set[str] = set()

    while queue:
        node = queue.pop(0)
        if node in visited:
            continue
        visited.add(node)
        ordered.append(node)
        for child in sorted(adjacency.get(node, []), key=_sort_key):
            indegree[child] = indegree.get(child, 0) - 1
            if indegree[child] <= 0 and child not in visited:
                queue.append(child)
        queue.sort(key=_sort_key)

    if len(ordered) < len(node_ids):
        leftover = sorted(node_ids - visited, key=_sort_key)
        ordered.extend(leftover)
    return ordered


def _load_concept(db: sqlite3.Connection, concept_id: str) -> Concept | None:
    row = db.execute("select * from concepts where id = ?", (concept_id,)).fetchone()
    if row is None:
        return None
    item_ids = [r["item_id"] for r in db.execute(
        "select item_id from concept_item where concept_id = ?",
        (concept_id,),
    ).fetchall()]
    neighbours = [r["b"] for r in db.execute(
        "select b from concept_edges where a = ? order by weight desc limit 5",
        (concept_id,),
    ).fetchall()]
    return Concept(
        id=row["id"],
        label=row["label"],
        summary=row["summary"],
        item_ids=item_ids,
        neighbors=neighbours,
        created_at=row["created_at"],
        **_concept_mastery_kwargs(row),
    )


def _learning_recommendation(gap_level: str, concept: Concept, language: str) -> str:
    if language == "zh-CN":
        mapping = {
            "no_knowledge": f"你多次检索「{concept.label}」但知识库里还没有任何内容，建议从权威来源抓 2–3 篇存入。",
            "shallow": f"关于「{concept.label}」的素材偏薄，建议补充一篇行业顶级资料并做一次总结。",
            "consolidate": f"对「{concept.label}」你已有足够素材，建议做一次 5 分钟闪卡回顾巩固。",
        }
    else:
        mapping = {
            "no_knowledge": f"You queried '{concept.label}' repeatedly with no library content. Capture 2–3 authoritative pages.",
            "shallow": f"Thin material on '{concept.label}'. Add one top-tier reference and write a summary.",
            "consolidate": f"You have enough on '{concept.label}'. Do a 5-minute flashcard review to consolidate.",
        }
    return mapping.get(gap_level, mapping["shallow"])


# ---------------------------------------------------------------------------
# Step 3: Retrieval practice helpers
# ---------------------------------------------------------------------------


def _generate_cloze(body: str, concept_label: str, language: str) -> list[str]:
    """Generate up to 3 cloze (fill-in-the-blank) questions from body text."""
    sentences = [s.strip() for s in re.split(r'[。.!！?？\n]', body) if len(s.strip()) > 15]
    if not sentences:
        if language == "zh-CN":
            return [f"请用一句话描述「{concept_label}」的核心含义。"]
        return [f"Describe the core meaning of '{concept_label}' in one sentence."]

    cloze: list[str] = []
    for sentence in sentences[:6]:
        # Find a key noun/term to blank out (longest token in the sentence)
        tokens = [t for t in tokenize(sentence) if t not in STOPWORDS and len(t) > 2]
        if not tokens:
            continue
        # Pick the longest token as the blank target
        target = max(tokens, key=len)
        blanked = sentence.replace(target, "______", 1)
        if blanked != sentence:
            if language == "zh-CN":
                cloze.append(f"填空：{blanked}")
            else:
                cloze.append(f"Fill in: {blanked}")
        if len(cloze) >= 3:
            break

    if not cloze:
        if language == "zh-CN":
            return [f"请用一句话描述「{concept_label}」的核心含义。"]
        return [f"Describe the core meaning of '{concept_label}' in one sentence."]
    return cloze


def _generate_counterexample(concept: Concept, language: str) -> str:
    """Generate a counterexample question based on concept neighbors."""
    if concept.neighbors:
        neighbor_label = concept.neighbors[0] if concept.neighbors else "unknown"
        if language == "zh-CN":
            return f"「{concept.label}」和相关概念有什么关键区别？在什么情况下它们会得出相反结论？"
        return f"What is the key difference between '{concept.label}' and related concepts? When would they lead to opposite conclusions?"
    if language == "zh-CN":
        return f"在什么情况下「{concept.label}」的结论会失效或不适用？"
    return f"Under what conditions would the conclusions about '{concept.label}' fail or not apply?"


def _generate_socratic(concept_label: str, item_title: str, language: str) -> str:
    """Generate a Socratic follow-up question."""
    if language == "zh-CN":
        return f"如果「{item_title}」中的核心约束发生变化，关于「{concept_label}」的结论还成立吗？为什么？"
    return f"If the core constraints in '{item_title}' changed, would the conclusions about '{concept_label}' still hold? Why or why not?"


# ---------------------------------------------------------------------------
# singleton
# ---------------------------------------------------------------------------


_CORE: KnowledgeCore | None = None


def default_core_path() -> Path:
    from ..storage import default_storage_path

    return default_storage_path().parent / "knowledge_core.sqlite3"


def get_core() -> KnowledgeCore:
    global _CORE
    if _CORE is None:
        _CORE = KnowledgeCore(path=default_core_path())
    return _CORE


def reset_core_for_tests(path: Path | str) -> KnowledgeCore:
    global _CORE
    _CORE = KnowledgeCore(path=path)
    return _CORE
