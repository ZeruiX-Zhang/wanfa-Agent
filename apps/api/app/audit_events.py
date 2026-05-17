"""Audit event-type catalog for the ``expert-coaching-loop`` feature.

Every state-changing operation introduced by the spec emits exactly one
``audit_log`` row with one of the constants defined here. Centralising
the strings prevents typos and gives Property 21 a single source of truth
to assert against (R13.1–R13.4).
"""

from __future__ import annotations

# CoachingSession lifecycle (R13.1).
COACHING_SESSION_CREATED = "coaching_session.created"
COACHING_SESSION_TRANSITION = "coaching_session_transition"
COACHING_SESSION_ARCHIVED = "coaching_session.archived"

# Mastery graph updates (R13.2). ``source`` payload key in
# ``{"practice", "decay", "experiment_review"}``.
MASTERY_UPDATE = "mastery_update"

# Calibration loop (R13.3).
CALIBRATION_RECORD = "calibration_record"

# Expert rubric loader (R13.4). ``status`` payload key in
# ``{"active", "refused", "superseded"}``.
RUBRIC_CHECK = "rubric_check"

# Skill chain transitions.
SKILL_CHAIN_ADVANCE = "skill_chain.advance"
SKILL_CHAIN_SWITCH = "skill_chain.switch"
SKILL_CHAIN_VALIDATION_ERROR = "skill_chain.validation_error"

# Active evidence gathering closure (R6, Property 15).
EVIDENCE_GATHERING_OPENED = "evidence_gathering.opened"
EVIDENCE_GATHERING_DISPATCHED = "evidence_gathering.dispatched"
EVIDENCE_GATHERING_PENDING = "evidence_gathering.pending"
EVIDENCE_GATHERING_APPROVED = "evidence_gathering.approved"
EVIDENCE_GATHERING_REJECTED = "evidence_gathering.rejected"
EVIDENCE_GATHERING_CLOSED = "evidence_gathering.closed"
EVIDENCE_GATHERING_ILLEGAL = "evidence_gathering.illegal_transition"

# Real-world result binding.
EXPERIMENT_REVIEW_RECORDED = "experiment_review.recorded"

# Metacognition hooks.
METACOGNITION_RECORDED = "metacognition.recorded"

# Startup / system safety.
SYSTEM_MISCONFIGURATION = "system.misconfiguration"


ALL_EVENT_TYPES: tuple[str, ...] = (
    COACHING_SESSION_CREATED,
    COACHING_SESSION_TRANSITION,
    COACHING_SESSION_ARCHIVED,
    MASTERY_UPDATE,
    CALIBRATION_RECORD,
    RUBRIC_CHECK,
    SKILL_CHAIN_ADVANCE,
    SKILL_CHAIN_SWITCH,
    SKILL_CHAIN_VALIDATION_ERROR,
    EVIDENCE_GATHERING_OPENED,
    EVIDENCE_GATHERING_DISPATCHED,
    EVIDENCE_GATHERING_PENDING,
    EVIDENCE_GATHERING_APPROVED,
    EVIDENCE_GATHERING_REJECTED,
    EVIDENCE_GATHERING_CLOSED,
    EVIDENCE_GATHERING_ILLEGAL,
    EXPERIMENT_REVIEW_RECORDED,
    METACOGNITION_RECORDED,
    SYSTEM_MISCONFIGURATION,
)
