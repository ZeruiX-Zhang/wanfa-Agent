"""Expert Rubric loader, version registry, and gap-scoring helpers.

Implements R2 (Expert Rubric and Gap Scoring) plus Property 7 (loader
robustness) and Property 8 (gap score bounds).

The loader reads YAML files from :data:`RUBRIC_ROOT` (``apps/api/expert_rubrics``)
and validates required fields. Refused rubrics fall back to ``default.yaml``
so :func:`apps.api.app.audit_agent.zero_context_audit` can keep running its
existing five dimensions even when a domain rubric is malformed (R2.5).
"""

from __future__ import annotations

import re
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Protocol

import yaml

from . import audit_events


RUBRIC_ROOT = Path(__file__).resolve().parent.parent / "expert_rubrics"


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RubricDimension:
    id: str
    weight: float
    anchors: tuple[str, ...]


@dataclass(frozen=True)
class ExpertRubric:
    id: str  # equals ``domain``
    domain: str
    version: str
    author: str
    source: str
    dimensions: tuple[RubricDimension, ...]
    examples: tuple[str, ...]
    cited_evidence_ids: tuple[str, ...]
    path: Path | None = None


@dataclass(frozen=True)
class ExpertGap:
    expert_gap_score: float
    missing_points: tuple[str, ...]
    rubric_id: str
    rubric_version: str
    rubric_source: str  # "domain" or "default"

    def to_dict(self) -> dict[str, Any]:
        return {
            "expert_gap_score": round(self.expert_gap_score, 3),
            "missing_points": list(self.missing_points),
            "rubric_id": self.rubric_id,
            "rubric_version": self.rubric_version,
            "rubric_source": self.rubric_source,
        }


@dataclass(frozen=True)
class RubricLoadResult:
    rubric: ExpertRubric | None
    status: str  # "active" | "refused"
    refused_reason: str | None = None
    refused_path: Path | None = None


# ---------------------------------------------------------------------------
# Tokenisation reused for anchor matching
# ---------------------------------------------------------------------------


_TOKEN_RE = re.compile(r"[\w]+", flags=re.UNICODE)
_STOPWORDS = {
    "the",
    "a",
    "an",
    "of",
    "to",
    "is",
    "and",
    "or",
    "for",
    "with",
    "in",
    "on",
}


def _tokenize(text: str) -> set[str]:
    if not text:
        return set()
    return {token.lower() for token in _TOKEN_RE.findall(text) if token.strip()} - _STOPWORDS


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------


class _Cache:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        # ``self._versions[domain]`` is an ordered list of (version, rubric).
        self._versions: dict[str, list[tuple[str, ExpertRubric]]] = {}
        self._refused: list[tuple[Path, str]] = []
        self._loaded_paths: set[Path] = set()


_CACHE = _Cache()


def _required(value: Any, field_name: str) -> Any:
    if value is None:
        raise ValueError(f"missing required field: {field_name}")
    if isinstance(value, str) and not value.strip():
        raise ValueError(f"empty required field: {field_name}")
    return value


def _parse_dimensions(raw: Any) -> tuple[RubricDimension, ...]:
    if not raw or not isinstance(raw, list):
        raise ValueError("dimensions must be a non-empty list")
    dims: list[RubricDimension] = []
    for entry in raw:
        if not isinstance(entry, dict):
            raise ValueError("each dimension must be a mapping")
        anchors = entry.get("anchors") or []
        if not isinstance(anchors, list) or not anchors:
            raise ValueError(f"dimension {entry.get('id')!r} needs at least one anchor")
        dims.append(
            RubricDimension(
                id=str(_required(entry.get("id"), "dimension.id")),
                weight=float(entry.get("weight", 0.0)),
                anchors=tuple(str(a) for a in anchors),
            )
        )
    return tuple(dims)


def _parse_payload(payload: Any, *, path: Path | None = None) -> ExpertRubric:
    """Build an :class:`ExpertRubric` from an already-loaded YAML payload.

    Shared between :func:`_parse_yaml` (file-based) and
    :func:`validate_yaml_text` (admin dry-run) so both paths apply
    *identical* validation rules (R2.1).
    """

    if not isinstance(payload, dict):
        raise ValueError("rubric file is not a YAML mapping")
    domain = str(_required(payload.get("domain"), "domain"))
    version = str(_required(payload.get("version"), "version"))
    author = str(_required(payload.get("author"), "author"))
    source = str(_required(payload.get("source"), "source"))
    cited = payload.get("cited_evidence_ids", [])
    if cited is None:
        cited = []
    if not isinstance(cited, list):
        raise ValueError("cited_evidence_ids must be a list")
    examples_raw = payload.get("examples", []) or []
    if not isinstance(examples_raw, list):
        raise ValueError("examples must be a list")
    return ExpertRubric(
        id=domain,
        domain=domain,
        version=version,
        author=author,
        source=source,
        dimensions=_parse_dimensions(payload.get("dimensions")),
        examples=tuple(str(e) for e in examples_raw),
        cited_evidence_ids=tuple(str(c) for c in cited),
        path=path,
    )


def _parse_yaml(path: Path) -> ExpertRubric:
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return _parse_payload(payload, path=path)


def _resolve_evidence_ids(
    cited: Iterable[str],
    *,
    evidence_resolver: callable | None,
) -> list[str]:
    """Return the subset of ``cited`` that does not resolve to evidence.

    The resolver is optional so unit tests can avoid spinning up
    ``KnowledgeCore``. When ``None`` we treat *no* ids as missing — runtime
    callers still pass a real resolver bound to ``EvidenceSnapshot`` /
    ``KnowledgeItem`` lookups.
    """

    if evidence_resolver is None:
        return []
    missing: list[str] = []
    for evidence_id in cited:
        try:
            ok = bool(evidence_resolver(evidence_id))
        except Exception:
            ok = False
        if not ok:
            missing.append(evidence_id)
    return missing


def load_rubric_file(
    path: Path,
    *,
    evidence_resolver: callable | None = None,
) -> RubricLoadResult:
    """Load a single rubric file with full validation."""

    try:
        rubric = _parse_yaml(path)
    except (yaml.YAMLError, ValueError) as exc:
        return RubricLoadResult(
            rubric=None,
            status="refused",
            refused_reason=f"parse_error: {exc}",
            refused_path=path,
        )

    missing = _resolve_evidence_ids(rubric.cited_evidence_ids, evidence_resolver=evidence_resolver)
    if missing:
        return RubricLoadResult(
            rubric=None,
            status="refused",
            refused_reason=f"unresolved_evidence_ids: {missing}",
            refused_path=path,
        )

    return RubricLoadResult(rubric=rubric, status="active")


def load_all(
    *,
    root: Path | None = None,
    evidence_resolver: callable | None = None,
    refresh: bool = False,
) -> list[RubricLoadResult]:
    """Load every YAML under :data:`RUBRIC_ROOT` (or ``root``) into the cache."""

    rubric_root = root or RUBRIC_ROOT
    results: list[RubricLoadResult] = []
    with _CACHE._lock:
        if refresh:
            _CACHE._versions.clear()
            _CACHE._refused.clear()
            _CACHE._loaded_paths.clear()
        for path in sorted(rubric_root.glob("*.yaml")):
            if path in _CACHE._loaded_paths and not refresh:
                continue
            result = load_rubric_file(path, evidence_resolver=evidence_resolver)
            results.append(result)
            if result.rubric is None:
                _CACHE._refused.append(
                    (result.refused_path or path, result.refused_reason or "unknown")
                )
                continue
            rubric = result.rubric
            versions = _CACHE._versions.setdefault(rubric.domain, [])
            # Replace existing version if a file is reloaded.
            versions[:] = [
                (v, r) for (v, r) in versions if v != rubric.version
            ]
            versions.append((rubric.version, rubric))
            _CACHE._loaded_paths.add(path)
    return results


def list_versions(domain: str) -> list[str]:
    with _CACHE._lock:
        return [v for (v, _) in _CACHE._versions.get(domain, [])]


def list_loaded() -> list[ExpertRubric]:
    """Return every currently-cached rubric across all domains.

    Used by ``GET /api/v2/rubrics`` to surface the active inventory plus
    any prior versions still kept readable for historical sessions
    (R2.6). The latest version of each domain comes last in the per-
    domain group; ordering between domains is alphabetical so the API
    response is stable.
    """

    with _CACHE._lock:
        out: list[ExpertRubric] = []
        for domain in sorted(_CACHE._versions):
            for _version, rubric in _CACHE._versions[domain]:
                out.append(rubric)
        return out


def rubric_to_dict(rubric: ExpertRubric) -> dict[str, Any]:
    """Serialize an :class:`ExpertRubric` for API responses.

    Mirrors the on-disk YAML schema (R2.1) plus convenience fields
    (``is_default``) the UI needs to render a "default fallback" badge.
    """

    return {
        "id": rubric.id,
        "domain": rubric.domain,
        "version": rubric.version,
        "author": rubric.author,
        "source": rubric.source,
        "dimensions": [
            {
                "id": dim.id,
                "weight": dim.weight,
                "anchors": list(dim.anchors),
            }
            for dim in rubric.dimensions
        ],
        "examples": list(rubric.examples),
        "cited_evidence_ids": list(rubric.cited_evidence_ids),
        "is_default": rubric.domain == "default",
    }


def validate_yaml_text(
    yaml_text: str,
    *,
    expected_domain: str | None = None,
    evidence_resolver: callable | None = None,
) -> tuple[bool, list[str], ExpertRubric | None]:
    """Dry-run validate a rubric YAML body without touching the cache or disk.

    Used by ``POST /api/v2/rubrics/check`` (R2.6 admin dry-run). Returns
    ``(valid, errors, rubric_preview)`` where ``rubric_preview`` is
    ``None`` whenever validation fails so callers cannot accidentally
    apply a partially-parsed rubric.

    The function is intentionally pure / side-effect-free: it does not
    register the rubric, does not write to disk, and does not mutate the
    ``_CACHE`` (R11.5 ``mode="dry-run"``).
    """

    errors: list[str] = []

    if not isinstance(yaml_text, str) or not yaml_text.strip():
        return False, ["yaml_text is empty"], None

    try:
        payload = yaml.safe_load(yaml_text)
    except yaml.YAMLError as exc:
        return False, [f"yaml_parse_error: {exc}"], None

    if payload is None:
        return False, ["yaml document is empty"], None

    try:
        rubric = _parse_payload(payload)
    except (ValueError, TypeError) as exc:
        return False, [f"schema_error: {exc}"], None

    if expected_domain is not None and rubric.domain != expected_domain:
        errors.append(
            f"domain_mismatch: payload domain {rubric.domain!r} does not match "
            f"expected {expected_domain!r}"
        )

    missing = _resolve_evidence_ids(
        rubric.cited_evidence_ids, evidence_resolver=evidence_resolver
    )
    if missing:
        errors.append(f"unresolved_evidence_ids: {missing}")

    if errors:
        return False, errors, None
    return True, [], rubric


def get_rubric(
    domain: str,
    *,
    version: str | None = None,
) -> ExpertRubric | None:
    """Return the rubric for ``(domain, version)`` if loaded.

    When ``version`` is omitted, the most recently registered version is
    returned. When the domain has no loaded rubric, ``None`` is returned —
    callers that want the safe fallback should call :func:`resolve_rubric`.
    """

    with _CACHE._lock:
        versions = list(_CACHE._versions.get(domain, []))
    if not versions:
        return None
    if version is None:
        return versions[-1][1]
    for v, rubric in versions:
        if v == version:
            return rubric
    return None


def resolve_rubric(
    domain: str | None,
    *,
    version: str | None = None,
) -> tuple[ExpertRubric | None, str]:
    """Return ``(rubric, source)`` where ``source`` ∈ {"domain", "default", "missing"}.

    Falls back to ``default.yaml`` when no domain rubric is registered
    (R2.7).
    """

    if domain:
        rubric = get_rubric(domain, version=version)
        if rubric is not None:
            return rubric, "domain"
    rubric = get_rubric("default")
    if rubric is not None:
        return rubric, "default"
    return None, "missing"


def refused_rubrics() -> list[tuple[Path, str]]:
    with _CACHE._lock:
        return list(_CACHE._refused)


def reset_cache_for_tests() -> None:
    with _CACHE._lock:
        _CACHE._versions.clear()
        _CACHE._refused.clear()
        _CACHE._loaded_paths.clear()


# ---------------------------------------------------------------------------
# Audit emission for rubric check events (R13.4, Task 2.19)
# ---------------------------------------------------------------------------


class _AuditSink(Protocol):
    """Minimal protocol for the ``KnowledgeCore._record_audit`` shape.

    Keeping :func:`record_rubric_check` decoupled from ``KnowledgeCore``
    lets tests pass an in-memory sink and lets the loader fall back to
    a no-op when no audit channel is configured (R13.4).
    """

    def _record_audit(
        self,
        *,
        tenant_id: str,
        actor: str,
        action: str,
        subject: str | None,
        payload: dict[str, Any] | None,
    ) -> str: ...


def record_rubric_check(
    *,
    core: _AuditSink | None,
    tenant_id: str,
    actor: str = "system",
    rubric: ExpertRubric | None,
    status: str,
    refused_reason: str | None = None,
    domain: str | None = None,
    version: str | None = None,
) -> str | None:
    """Emit a ``rubric_check`` audit row (R13.4).

    The payload always carries the documented keys: ``domain``,
    ``version``, ``status``, and ``cited_evidence_ids``. ``status`` is one
    of ``{"active", "refused", "applied", "superseded"}`` per the
    design.md "Audit log event_type catalogue" entry.

    When ``core`` is ``None`` (e.g. unit tests that don't spin up the
    full ``KnowledgeCore``) the function returns ``None`` rather than
    raising, so callers can wire it unconditionally.
    """

    if core is None:
        return None
    payload_domain = domain or (rubric.domain if rubric else "unknown")
    payload_version = version or (rubric.version if rubric else "unknown")
    cited = list(rubric.cited_evidence_ids) if rubric else []
    payload: dict[str, Any] = {
        "domain": payload_domain,
        "version": payload_version,
        "status": status,
        "cited_evidence_ids": cited,
    }
    if refused_reason:
        payload["refused_reason"] = refused_reason
    try:
        return core._record_audit(
            tenant_id=tenant_id,
            actor=actor,
            action=audit_events.RUBRIC_CHECK,
            subject=payload_domain,
            payload=payload,
        )
    except Exception:
        # Audit is best-effort — never block the loader on logging.
        return None


def load_all_with_audit(
    *,
    core: _AuditSink | None,
    tenant_id: str,
    actor: str = "system",
    root: Path | None = None,
    evidence_resolver: callable | None = None,
    refresh: bool = False,
) -> list[RubricLoadResult]:
    """Like :func:`load_all`, but emits one ``rubric_check`` row per file.

    Each loaded rubric produces a ``status="active"`` audit row; each
    refused rubric produces a ``status="refused"`` row with the
    ``refused_reason`` payload key (R2.5, R13.4).
    """

    results = load_all(
        root=root, evidence_resolver=evidence_resolver, refresh=refresh
    )
    for result in results:
        if result.rubric is not None:
            record_rubric_check(
                core=core,
                tenant_id=tenant_id,
                actor=actor,
                rubric=result.rubric,
                status="active",
            )
        else:
            record_rubric_check(
                core=core,
                tenant_id=tenant_id,
                actor=actor,
                rubric=None,
                status="refused",
                refused_reason=result.refused_reason,
                domain=str(result.refused_path) if result.refused_path else None,
                version="unknown",
            )
    return results


# ---------------------------------------------------------------------------
# Gap scoring (Property 8)
# ---------------------------------------------------------------------------


def expert_gap_score(answer_text: str, rubric: ExpertRubric, *, max_missing: int = 7) -> ExpertGap:
    """Return ``(expert_gap_score, missing_points)`` for an answer.

    Pure function. For every dimension we count anchors that share at least
    one token with the answer text. The dimension's contribution is
    ``hits/total * weight``; the final score is the weighted ratio capped
    to ``[0, 1]``.
    """

    answer_tokens = _tokenize(answer_text)
    weight_total = sum(d.weight for d in rubric.dimensions) or 1.0
    score_total = 0.0
    missing: list[str] = []
    for dim in rubric.dimensions:
        anchor_total = max(len(dim.anchors), 1)
        hits = 0
        for anchor in dim.anchors:
            anchor_tokens = _tokenize(anchor)
            if anchor_tokens and (answer_tokens & anchor_tokens):
                hits += 1
            else:
                missing.append(f"[{dim.id}] {anchor}")
        score_total += (hits / anchor_total) * dim.weight
    score = max(0.0, min(1.0, score_total / weight_total))
    rubric_source = "default" if rubric.domain == "default" else "domain"
    return ExpertGap(
        expert_gap_score=score,
        missing_points=tuple(missing[:max_missing]),
        rubric_id=rubric.id,
        rubric_version=rubric.version,
        rubric_source=rubric_source,
    )


__all__ = [
    "RUBRIC_ROOT",
    "RubricDimension",
    "ExpertRubric",
    "ExpertGap",
    "RubricLoadResult",
    "load_rubric_file",
    "load_all",
    "load_all_with_audit",
    "list_versions",
    "list_loaded",
    "get_rubric",
    "resolve_rubric",
    "refused_rubrics",
    "reset_cache_for_tests",
    "expert_gap_score",
    "rubric_to_dict",
    "validate_yaml_text",
    "record_rubric_check",
]
