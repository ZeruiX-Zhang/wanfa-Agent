"""Evaluation harness — the minimum system to avoid "failure point 4".

Four metrics, each computed deterministically from the SQLite state we already
maintain. No external services required; LangSmith / RAGAS can be layered on
later by writing parallel implementations that satisfy the same payload shape.

Metrics (all in [0, 1]):

* **citation_coverage** — for every ``ask`` event in audit, what fraction
  produced at least one citation.
* **evidence_presence** — for every ``ask`` event, what fraction produced
  ``confidence_band != "insufficient"``. This is the opposite of
  hallucination-risk.
* **action_adoption** — for every experiment created, what fraction the user
  flipped out of ``planned`` (i.e. started running / reported result).
* **review_closure** — for every non-planned experiment, what fraction has a
  matching learning review. Closes the Layer 7 loop.

Plus an advisory field ``sample_size`` per metric so the UI can warn when
numbers are computed on thin data.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from typing import Any

from .knowledge_core import KnowledgeCore


@dataclass(frozen=True)
class MetricResult:
    id: str
    label_zh: str
    label_en: str
    value: float
    sample_size: int
    description_zh: str
    description_en: str
    tier: str  # "green" | "amber" | "red" | "unknown"

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label_zh": self.label_zh,
            "label_en": self.label_en,
            "value": round(self.value, 3),
            "sample_size": self.sample_size,
            "description_zh": self.description_zh,
            "description_en": self.description_en,
            "tier": self.tier,
        }


def _tier(value: float, sample_size: int, green: float, amber: float) -> str:
    if sample_size == 0:
        return "unknown"
    if value >= green:
        return "green"
    if value >= amber:
        return "amber"
    return "red"


def _tier_inverted(value: float, sample_size: int, green: float, amber: float) -> str:
    """For metrics where higher is better (like human override rate)."""
    if sample_size == 0:
        return "unknown"
    if value >= green:
        return "green"
    if value >= amber:
        return "amber"
    return "red"


def compute_metrics(*, core: KnowledgeCore, tenant_id: str) -> list[MetricResult]:
    """Compute the five core metrics for a tenant from on-disk state."""

    with core._lock, core._connect() as db:
        citation_coverage, citation_sample = _ask_citation_coverage(db, tenant_id)
        evidence_presence, evidence_sample = _ask_evidence_presence(db, tenant_id)
        adoption, adoption_sample = _action_adoption(db, tenant_id)
        closure, closure_sample = _review_closure(db, tenant_id)
        override_rate, override_sample = _human_override_rate(db, tenant_id)

    return [
        MetricResult(
            id="citation_coverage",
            label_zh="引用完整率",
            label_en="Citation coverage",
            value=citation_coverage,
            sample_size=citation_sample,
            description_zh="有多少次问答给出了至少一条证据引用；偏低说明知识库在相关主题上覆盖不够。",
            description_en="Fraction of asks that returned at least one citation. Low means your library is thin on those topics.",
            tier=_tier(citation_coverage, citation_sample, 0.7, 0.4),
        ),
        MetricResult(
            id="evidence_presence",
            label_zh="证据充分率",
            label_en="Evidence presence",
            value=evidence_presence,
            sample_size=evidence_sample,
            description_zh="有多少次问答置信带不是 insufficient；这是系统「不知道就说不知道」的反面。",
            description_en="Fraction of asks where confidence was not 'insufficient'. Inverse of hallucination risk.",
            tier=_tier(evidence_presence, evidence_sample, 0.6, 0.3),
        ),
        MetricResult(
            id="action_adoption",
            label_zh="建议采纳率",
            label_en="Action adoption",
            value=adoption,
            sample_size=adoption_sample,
            description_zh="有多少建议的最小实验被你真的跑起来了；低说明建议不够贴合现实或你没在用。",
            description_en="Fraction of suggested experiments you actually started. Low = advice not actionable or not used.",
            tier=_tier(adoption, adoption_sample, 0.5, 0.25),
        ),
        MetricResult(
            id="review_closure",
            label_zh="复盘闭环率",
            label_en="Review closure",
            value=closure,
            sample_size=closure_sample,
            description_zh="启动的实验里有多少做过复盘；低说明学习闭环在漏，知识没回流进库。",
            description_en="Fraction of started experiments that got a learning review. Low = learning loop leaks.",
            tier=_tier(closure, closure_sample, 0.6, 0.3),
        ),
        MetricResult(
            id="human_override_rate",
            label_zh="人类审查率",
            label_en="Human override rate",
            value=override_rate,
            sample_size=override_sample,
            description_zh="诊断中有多少决策锚点被用户修改或拒绝；越高说明用户在主动思考而非盲从 Agent。",
            description_en="Fraction of decision anchors the user overrode or rejected. Higher = user is thinking critically, not outsourcing judgment.",
            tier=_tier_inverted(override_rate, override_sample, 0.2, 0.05),
        ),
    ]


def _ask_citation_coverage(db: sqlite3.Connection, tenant_id: str) -> tuple[float, int]:
    rows = db.execute(
        "select payload_json from audit_log where tenant_id = ? and action = 'ask'",
        (tenant_id,),
    ).fetchall()
    if not rows:
        return 0.0, 0
    with_citation = 0
    for row in rows:
        try:
            payload = json.loads(row["payload_json"] or "{}")
        except json.JSONDecodeError:
            payload = {}
        if int(payload.get("citation_count", 0) or 0) >= 1:
            with_citation += 1
    return with_citation / len(rows), len(rows)


def _ask_evidence_presence(db: sqlite3.Connection, tenant_id: str) -> tuple[float, int]:
    rows = db.execute(
        "select payload_json from audit_log where tenant_id = ? and action = 'ask'",
        (tenant_id,),
    ).fetchall()
    if not rows:
        return 0.0, 0
    sufficient = 0
    for row in rows:
        try:
            payload = json.loads(row["payload_json"] or "{}")
        except json.JSONDecodeError:
            payload = {}
        band = str(payload.get("confidence_band") or "")
        if band and band != "insufficient":
            sufficient += 1
    return sufficient / len(rows), len(rows)


def _action_adoption(db: sqlite3.Connection, tenant_id: str) -> tuple[float, int]:
    try:
        rows = db.execute(
            "select status from experiments where tenant_id = ?",
            (tenant_id,),
        ).fetchall()
    except sqlite3.OperationalError:
        return 0.0, 0
    if not rows:
        return 0.0, 0
    adopted = sum(1 for row in rows if str(row["status"]) != "planned")
    return adopted / len(rows), len(rows)


def _review_closure(db: sqlite3.Connection, tenant_id: str) -> tuple[float, int]:
    try:
        started = db.execute(
            "select id from experiments where tenant_id = ? and status != 'planned'",
            (tenant_id,),
        ).fetchall()
        reviewed_rows = db.execute(
            "select experiment_id from learning_reviews where tenant_id = ? and experiment_id is not null",
            (tenant_id,),
        ).fetchall()
    except sqlite3.OperationalError:
        return 0.0, 0
    if not started:
        return 0.0, 0
    reviewed_ids = {row["experiment_id"] for row in reviewed_rows}
    closed = sum(1 for row in started if row["id"] in reviewed_ids)
    return closed / len(started), len(started)


def _human_override_rate(db: sqlite3.Connection, tenant_id: str) -> tuple[float, int]:
    """Compute the fraction of diagnose events where the user overrode anchors.

    Reads from audit_log entries with action='diagnose_anchor_response'.
    Each such entry has payload with anchors_accepted and anchors_overridden counts.
    A higher override rate is healthy — it means the user is thinking critically.
    """
    try:
        rows = db.execute(
            "select payload_json from audit_log where tenant_id = ? and action = 'diagnose_anchor_response'",
            (tenant_id,),
        ).fetchall()
    except sqlite3.OperationalError:
        return 0.0, 0
    if not rows:
        return 0.0, 0
    total_anchors = 0
    overridden_anchors = 0
    for row in rows:
        try:
            payload = json.loads(row["payload_json"] or "{}")
        except json.JSONDecodeError:
            continue
        accepted = int(payload.get("anchors_accepted_by_human", 0))
        overridden = int(payload.get("anchors_overridden_by_human", 0))
        total_anchors += accepted + overridden
        overridden_anchors += overridden
    if total_anchors == 0:
        return 0.0, 0
    return overridden_anchors / total_anchors, total_anchors


__all__ = ["MetricResult", "compute_metrics"]
