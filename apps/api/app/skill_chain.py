"""Skill Chain definitions, loader, and pure transition functions.

Implements R3 (Skill Chain) and Properties 9 (transition validity).

The loader reads YAML files from
:data:`CHAIN_ROOT` (``apps/api/thinking_skills/chains``) and validates
that every ``skill_id`` resolves to an existing skill folder under
``apps/api/thinking_skills`` (R3.7). The transition function is pure so
the orchestrator can call it freely and PBT can drive it deterministically.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Protocol

import yaml

from . import audit_events


# ---------------------------------------------------------------------------
# Paths and registry
# ---------------------------------------------------------------------------


THINKING_SKILLS_ROOT = Path(__file__).resolve().parent.parent / "thinking_skills"
CHAIN_ROOT = THINKING_SKILLS_ROOT / "chains"


def _existing_skill_ids(root: Path | None = None) -> set[str]:
    skills_root = root or THINKING_SKILLS_ROOT
    found: set[str] = set()
    if not skills_root.exists():
        return found
    for child in skills_root.iterdir():
        if not child.is_dir():
            continue
        if child.name == "chains":
            continue
        # ``search`` and ``validation`` ship sub-skills but no SKILL.md at the
        # top level. Treat the top-level folder name as the skill id and also
        # pick up direct sub-skills.
        if (child / "SKILL.md").exists():
            found.add(child.name)
        for sub in child.iterdir():
            if sub.is_dir() and (sub / "SKILL.md").exists():
                found.add(sub.name)
    return found


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


# Predicate names referenced by chain YAMLs. The orchestrator supplies a
# context dict keyed by these names so the chain stays declarative.
ChainPredicate = str

ALWAYS = "always"


@dataclass(frozen=True)
class ChainStep:
    skill_id: str
    description: str
    entry_conditions: tuple[ChainPredicate, ...]
    exit_conditions: tuple[ChainPredicate, ...]


@dataclass(frozen=True)
class SkillChain:
    id: str
    problem_type: str
    description: str
    steps: tuple[ChainStep, ...]
    entry_conditions: tuple[ChainPredicate, ...]
    path: Path | None = None


@dataclass(frozen=True)
class SkillChainState:
    chain_id: str
    step_idx: int
    step_skill_id: str
    entry_satisfied: bool
    exit_satisfied: bool


@dataclass(frozen=True)
class TransitionResult:
    advance: bool = False
    repeat: bool = False
    propose_switch: bool = False
    switched: bool = False
    next_state: SkillChainState | None = None
    reason: str | None = None
    new_problem_type: str | None = None


class SkillChainValidationError(ValueError):
    """Raised at startup when a chain references an unknown skill (R3.7)."""


# ---------------------------------------------------------------------------
# Predicate evaluation
# ---------------------------------------------------------------------------


def evaluate_predicates(
    predicates: Iterable[ChainPredicate],
    context: Mapping[str, Any],
) -> bool:
    """Return ``True`` iff every predicate evaluates true under ``context``.

    Predicate semantics:
    - ``"always"`` → always true.
    - ``"key"`` (no operator) → ``bool(context[key])``.
    - ``"!key"`` → not ``bool(context[key])``.
    - ``"key=value"`` → ``str(context[key]) == value``.
    """

    for predicate in predicates:
        if not _eval_one(predicate, context):
            return False
    return True


def _eval_one(predicate: ChainPredicate, context: Mapping[str, Any]) -> bool:
    name = predicate.strip()
    if not name or name == ALWAYS:
        return True
    if name.startswith("!"):
        return not bool(context.get(name[1:].strip()))
    if "=" in name:
        key, _, value = name.partition("=")
        return str(context.get(key.strip())) == value.strip()
    return bool(context.get(name))


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------


class _Cache:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._chains: dict[str, SkillChain] = {}
        self._refused: list[tuple[Path, str]] = []
        self._loaded_paths: set[Path] = set()


_CACHE = _Cache()


def _parse_step(raw: Mapping[str, Any]) -> ChainStep:
    skill_id = str(raw.get("skill_id") or "")
    if not skill_id:
        raise ValueError("step is missing skill_id")
    return ChainStep(
        skill_id=skill_id,
        description=str(raw.get("description") or ""),
        entry_conditions=tuple(str(p) for p in (raw.get("entry_conditions") or [ALWAYS])),
        exit_conditions=tuple(str(p) for p in (raw.get("exit_conditions") or [])),
    )


def _parse_chain(path: Path) -> SkillChain:
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        raise ValueError("chain file is not a YAML mapping")
    chain_id = str(payload.get("id") or "")
    problem_type = str(payload.get("problem_type") or "")
    if not chain_id or not problem_type:
        raise ValueError("chain requires id and problem_type")
    steps_raw = payload.get("steps") or []
    if not isinstance(steps_raw, list) or not steps_raw:
        raise ValueError("chain.steps must be a non-empty list")
    steps = tuple(_parse_step(step) for step in steps_raw)
    return SkillChain(
        id=chain_id,
        problem_type=problem_type,
        description=str(payload.get("description") or ""),
        steps=steps,
        entry_conditions=tuple(
            str(p) for p in (payload.get("entry_conditions") or [ALWAYS])
        ),
        path=path,
    )


def load_all(
    *,
    root: Path | None = None,
    skill_ids: set[str] | None = None,
    refresh: bool = False,
) -> dict[str, SkillChain]:
    """Load every chain YAML in ``root`` (default :data:`CHAIN_ROOT`)."""

    chain_root = root or CHAIN_ROOT
    valid_skills = skill_ids if skill_ids is not None else _existing_skill_ids()
    with _CACHE._lock:
        if refresh:
            _CACHE._chains.clear()
            _CACHE._refused.clear()
            _CACHE._loaded_paths.clear()
        if not chain_root.exists():
            return dict(_CACHE._chains)
        for path in sorted(chain_root.glob("*.yaml")):
            if path in _CACHE._loaded_paths and not refresh:
                continue
            try:
                chain = _parse_chain(path)
            except (yaml.YAMLError, ValueError) as exc:
                _CACHE._refused.append((path, f"parse_error: {exc}"))
                continue
            unknown = [s.skill_id for s in chain.steps if s.skill_id not in valid_skills]
            if unknown:
                # R3.7 — refuse to load and surface the validation error.
                _CACHE._refused.append((path, f"unknown_skill_ids: {unknown}"))
                continue
            _CACHE._chains[chain.id] = chain
            _CACHE._loaded_paths.add(path)
        return dict(_CACHE._chains)


def list_chains() -> list[SkillChain]:
    with _CACHE._lock:
        return list(_CACHE._chains.values())


def get_chain(chain_id: str) -> SkillChain | None:
    with _CACHE._lock:
        return _CACHE._chains.get(chain_id)


def refused_chains() -> list[tuple[Path, str]]:
    with _CACHE._lock:
        return list(_CACHE._refused)


def reset_cache_for_tests() -> None:
    with _CACHE._lock:
        _CACHE._chains.clear()
        _CACHE._refused.clear()
        _CACHE._loaded_paths.clear()


# ---------------------------------------------------------------------------
# Selection + transition (Property 9)
# ---------------------------------------------------------------------------


def select_chain(
    *,
    problem_type: str,
    chains: Iterable[SkillChain],
    context: Mapping[str, Any],
) -> SkillChain | None:
    """Return the first chain whose ``problem_type`` matches and whose
    chain-level ``entry_conditions`` all hold under ``context``.

    Falls back to ``general_decision`` when no problem-typed chain qualifies
    (R3.6). Returns ``None`` when no chain registry is available.
    """

    chains_list = list(chains)
    if not chains_list:
        return None
    candidates = [c for c in chains_list if c.problem_type == problem_type]
    candidates += [c for c in chains_list if c.problem_type == "general"]
    for chain in candidates:
        if evaluate_predicates(chain.entry_conditions, context):
            return chain
    for chain in chains_list:
        if chain.id == "general_decision":
            return chain
    return chains_list[0]


def initial_state(chain: SkillChain, context: Mapping[str, Any]) -> SkillChainState:
    first = chain.steps[0]
    return SkillChainState(
        chain_id=chain.id,
        step_idx=0,
        step_skill_id=first.skill_id,
        entry_satisfied=evaluate_predicates(first.entry_conditions, context),
        exit_satisfied=evaluate_predicates(first.exit_conditions, context),
    )


def transition(
    *,
    chain: SkillChain,
    state: SkillChainState,
    context: Mapping[str, Any],
    failures: int = 0,
    failure_threshold: int = 2,
    new_problem_type: str | None = None,
    auto_switch: bool = False,
    chains: Iterable[SkillChain] | None = None,
) -> TransitionResult:
    """Return the next :class:`TransitionResult` for ``state``.

    The function is pure: it reads from ``context`` and the chain registry
    but does not mutate either.
    """

    step = chain.steps[state.step_idx]
    exit_now = evaluate_predicates(step.exit_conditions, context)

    if exit_now and state.step_idx + 1 < len(chain.steps):
        next_step = chain.steps[state.step_idx + 1]
        next_state = SkillChainState(
            chain_id=chain.id,
            step_idx=state.step_idx + 1,
            step_skill_id=next_step.skill_id,
            entry_satisfied=evaluate_predicates(next_step.entry_conditions, context),
            exit_satisfied=evaluate_predicates(next_step.exit_conditions, context),
        )
        return TransitionResult(advance=True, next_state=next_state)

    if failures >= failure_threshold:
        target = _pick_switch_target(
            current=chain,
            context=context,
            chains=chains or list_chains(),
            new_problem_type=new_problem_type,
        )
        if target is not None and target.id != chain.id:
            return TransitionResult(
                switched=True,
                next_state=initial_state(target, context),
                reason="consecutive_failures",
            )

    if new_problem_type and new_problem_type != chain.problem_type:
        if auto_switch:
            target = _pick_switch_target(
                current=chain,
                context=context,
                chains=chains or list_chains(),
                new_problem_type=new_problem_type,
            )
            if target is not None and target.id != chain.id:
                return TransitionResult(
                    switched=True,
                    next_state=initial_state(target, context),
                    reason="problem_type_change",
                    new_problem_type=new_problem_type,
                )
        return TransitionResult(
            propose_switch=True,
            new_problem_type=new_problem_type,
            next_state=state,
        )

    # Repeat the current step with refined prompts (R3.3).
    refreshed = SkillChainState(
        chain_id=chain.id,
        step_idx=state.step_idx,
        step_skill_id=step.skill_id,
        entry_satisfied=evaluate_predicates(step.entry_conditions, context),
        exit_satisfied=exit_now,
    )
    return TransitionResult(repeat=True, next_state=refreshed)


def _pick_switch_target(
    *,
    current: SkillChain,
    context: Mapping[str, Any],
    chains: Iterable[SkillChain],
    new_problem_type: str | None = None,
) -> SkillChain | None:
    chains_list = [c for c in chains if c.id != current.id]
    if not chains_list:
        return None
    if new_problem_type:
        target = next(
            (
                c
                for c in chains_list
                if c.problem_type == new_problem_type
                and evaluate_predicates(c.entry_conditions, context)
            ),
            None,
        )
        if target is not None:
            return target
    target = next(
        (c for c in chains_list if evaluate_predicates(c.entry_conditions, context)),
        None,
    )
    return target


# ---------------------------------------------------------------------------
# Audit emission for skill chain transitions (R13.1, Task 2.19)
# ---------------------------------------------------------------------------


class _AuditSink(Protocol):
    """Minimal protocol for ``KnowledgeCore._record_audit``.

    Keeping the audit emission decoupled from the storage layer lets the
    pure transition logic above stay PBT-friendly while still letting
    M1's coach-turn write path emit ``skill_chain.advance`` /
    ``skill_chain.switch`` rows (R13.1).
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


def record_advance(
    *,
    core: _AuditSink | None,
    tenant_id: str,
    actor: str = "system",
    session_id: str,
    chain_id: str,
    prev_idx: int,
    next_idx: int,
) -> str | None:
    """Emit a ``skill_chain.advance`` audit row.

    Payload carries ``session_id``, ``chain_id``, ``prev_idx``, ``next_idx``
    per the design.md "Audit log event_type catalogue" entry.
    """

    if core is None:
        return None
    payload: dict[str, Any] = {
        "session_id": session_id,
        "chain_id": chain_id,
        "prev_idx": prev_idx,
        "next_idx": next_idx,
    }
    try:
        return core._record_audit(
            tenant_id=tenant_id,
            actor=actor,
            action=audit_events.SKILL_CHAIN_ADVANCE,
            subject=session_id,
            payload=payload,
        )
    except Exception:
        return None


def record_switch(
    *,
    core: _AuditSink | None,
    tenant_id: str,
    actor: str = "system",
    session_id: str,
    from_chain: str,
    to_chain: str,
    trigger_reason: str,
) -> str | None:
    """Emit a ``skill_chain.switch`` audit row.

    Payload carries ``session_id``, ``from_chain``, ``to_chain``,
    ``trigger_reason`` per design.md "Audit log event_type catalogue".
    """

    if core is None:
        return None
    payload: dict[str, Any] = {
        "session_id": session_id,
        "from_chain": from_chain,
        "to_chain": to_chain,
        "trigger_reason": trigger_reason,
    }
    try:
        return core._record_audit(
            tenant_id=tenant_id,
            actor=actor,
            action=audit_events.SKILL_CHAIN_SWITCH,
            subject=session_id,
            payload=payload,
        )
    except Exception:
        return None


def transition_with_audit(
    *,
    core: _AuditSink | None,
    tenant_id: str,
    actor: str = "system",
    session_id: str,
    chain: SkillChain,
    state: SkillChainState,
    context: Mapping[str, Any],
    failures: int = 0,
    failure_threshold: int = 2,
    new_problem_type: str | None = None,
    auto_switch: bool = False,
    chains: Iterable[SkillChain] | None = None,
) -> TransitionResult:
    """Wrap :func:`transition` and emit one audit row per state change.

    Pure :func:`transition` is preserved so PBTs keep their isolation.
    Production callers that need audit semantics use this helper instead.
    A ``advance`` row is emitted iff ``result.advance`` is true; a
    ``switch`` row is emitted iff ``result.switched`` is true. ``repeat``
    and ``propose_switch`` results emit no audit row (R13.1 — one row per
    accepted state change).
    """

    result = transition(
        chain=chain,
        state=state,
        context=context,
        failures=failures,
        failure_threshold=failure_threshold,
        new_problem_type=new_problem_type,
        auto_switch=auto_switch,
        chains=chains,
    )

    if result.advance and result.next_state is not None:
        record_advance(
            core=core,
            tenant_id=tenant_id,
            actor=actor,
            session_id=session_id,
            chain_id=chain.id,
            prev_idx=state.step_idx,
            next_idx=result.next_state.step_idx,
        )
    elif result.switched and result.next_state is not None:
        record_switch(
            core=core,
            tenant_id=tenant_id,
            actor=actor,
            session_id=session_id,
            from_chain=chain.id,
            to_chain=result.next_state.chain_id,
            trigger_reason=result.reason or "unspecified",
        )
    return result


# ---------------------------------------------------------------------------
# Consecutive-fail policy (Task 4.12, R9.3, R9.4)
# ---------------------------------------------------------------------------


def count_trailing_fails(result_classes: "list[str]") -> int:
    """Count consecutive ``"fail"`` outcomes at the tail of the history.

    A single non-fail outcome resets the streak. Used to decide when the
    consecutive-fail policy fires (Property 20).
    """

    streak = 0
    for outcome in reversed(result_classes):
        if outcome == "fail":
            streak += 1
        else:
            break
    return streak


def consecutive_fail_policy(
    *,
    trailing_fails: int,
    threshold: int = 3,
    policy: str = "chain_switch",
) -> str | None:
    """Decide the response to ``K`` trailing experiment failures (R9.3, R9.4).

    Returns ``"chain_switch"`` or ``"human_review_required"`` once
    ``trailing_fails`` reaches ``threshold`` (default 3), or ``None``
    while the streak is still below it. ``policy="human_review"`` selects
    the human-review escalation; any other value defaults to switching
    the skill chain.
    """

    if trailing_fails < max(1, threshold):
        return None
    if policy == "human_review":
        return "human_review_required"
    return "chain_switch"


__all__ = [
    "CHAIN_ROOT",
    "THINKING_SKILLS_ROOT",
    "ChainStep",
    "SkillChain",
    "SkillChainState",
    "TransitionResult",
    "SkillChainValidationError",
    "evaluate_predicates",
    "load_all",
    "list_chains",
    "get_chain",
    "refused_chains",
    "reset_cache_for_tests",
    "select_chain",
    "initial_state",
    "transition",
    "transition_with_audit",
    "record_advance",
    "record_switch",
    "count_trailing_fails",
    "consecutive_fail_policy",
]
