"""Property-based tests for the Skill Chain transition function.

Feature: expert-coaching-loop, Property 9: Skill chain transition validity
Validates: Requirements 3.3, 3.4, 3.5, 3.7, 17.4
"""

from __future__ import annotations

from typing import Mapping

import pytest
from hypothesis import HealthCheck, given, settings, strategies as st

from apps.api.app import skill_chain


def _registry() -> list[skill_chain.SkillChain]:
    skill_chain.reset_cache_for_tests()
    skill_chain.load_all(refresh=True)
    return skill_chain.list_chains()


def _gate(name: str, *, condition: str = "always") -> skill_chain.ChainStep:
    return skill_chain.ChainStep(
        skill_id=name,
        description="",
        entry_conditions=("always",),
        exit_conditions=(condition,) if condition else ("always",),
    )


def _chain(*, problem_type: str, exit_conditions=("always",)) -> skill_chain.SkillChain:
    return skill_chain.SkillChain(
        id=f"{problem_type}_chain",
        problem_type=problem_type,
        description="",
        steps=(
            _gate("problem-statement", condition=exit_conditions[0]),
            _gate("five-whys", condition=exit_conditions[0]),
        ),
        entry_conditions=("always",),
    )


def _make_state(chain: skill_chain.SkillChain) -> skill_chain.SkillChainState:
    return skill_chain.initial_state(chain, {"always": True})


@settings(max_examples=200, deadline=None,
          suppress_health_check=[HealthCheck.too_slow])
@given(
    failures=st.integers(min_value=0, max_value=5),
    new_problem_type=st.sampled_from(["general", "troubleshooting", "other", None]),
    auto_switch=st.booleans(),
    exit_satisfied=st.booleans(),
)
def test_property_9_transition_invariants(
    failures: int,
    new_problem_type: str | None,
    auto_switch: bool,
    exit_satisfied: bool,
) -> None:
    chains = [
        _chain(problem_type="general"),
        _chain(problem_type="troubleshooting"),
    ]
    chain = chains[0]
    state = _make_state(chain)
    context: Mapping[str, object] = {"always": exit_satisfied}

    # Force the exit gate via the always alias so the test toggles
    # ``exit_satisfied`` deterministically.
    if exit_satisfied:
        # Replace the chain with one whose exit is always satisfied to model
        # "step exit met". We mutate via a fresh chain instance.
        chain = skill_chain.SkillChain(
            id="general_chain",
            problem_type="general",
            description="",
            steps=(
                skill_chain.ChainStep(
                    skill_id="problem-statement",
                    description="",
                    entry_conditions=("always",),
                    exit_conditions=("always",),
                ),
                skill_chain.ChainStep(
                    skill_id="five-whys",
                    description="",
                    entry_conditions=("always",),
                    exit_conditions=("always",),
                ),
            ),
            entry_conditions=("always",),
        )
        chains[0] = chain
        state = _make_state(chain)

    result = skill_chain.transition(
        chain=chain,
        state=state,
        context=context,
        failures=failures,
        failure_threshold=2,
        new_problem_type=new_problem_type,
        auto_switch=auto_switch,
        chains=chains,
    )

    # Exactly one of advance/repeat/propose_switch/switched is True.
    flags = [result.advance, result.repeat, result.propose_switch, result.switched]
    assert sum(flags) == 1, f"exactly one outcome, got {flags}"

    if result.advance:
        assert result.next_state is not None
        assert result.next_state.step_idx == state.step_idx + 1
        assert result.next_state.chain_id == chain.id

    if result.switched:
        assert result.next_state is not None
        target = next(c for c in chains if c.id == result.next_state.chain_id)
        # Property 9c: the switch lands on a chain whose entry conditions hold.
        assert skill_chain.evaluate_predicates(target.entry_conditions, context)

    if result.propose_switch:
        # Caller has not committed; state is unchanged.
        assert result.next_state == state


def test_select_chain_falls_back_to_general_decision() -> None:
    chains = _registry()
    chain = skill_chain.select_chain(
        problem_type="some_unknown_type", chains=chains, context={}
    )
    assert chain is not None
    assert chain.id == "general_decision"


def test_select_chain_matches_problem_type() -> None:
    chains = _registry()
    chain = skill_chain.select_chain(
        problem_type="troubleshooting", chains=chains, context={}
    )
    assert chain is not None
    assert chain.id == "troubleshooting"
