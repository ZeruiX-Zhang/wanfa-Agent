"""i18n parity test for the Web bundle (Task 2.16).

This test parses ``apps/web/lib/i18n.ts`` directly as text so we don't need a
Node toolchain in the Python test environment. The bundle is structured so
each top-level dictionary literal (``const zhCN: Dictionary = { ... }`` and
``const enUS: Dictionary = { ... }``) contains only string-to-string
key/value pairs, which makes a small brace-balanced scan safe.

Asserts (per Task 2.16 / Requirements 14.1-3):
- Every key in ``zhCN`` is also in ``enUS`` (and vice versa).
- The new ``coach.* / rubrics.*`` keys introduced by the expert-coaching-loop
  M1 milestone are present in both dictionaries.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
I18N_FILE = REPO_ROOT / "apps" / "web" / "lib" / "i18n.ts"


# Required keys for the expert-coaching-loop P0 milestone (coach / rubric /
# skill-chain). Matches the design.md "i18n entry" section verbatim.
REQUIRED_COACH_KEYS: frozenset[str] = frozenset(
    {
        "coach.next_action.learn",
        "coach.next_action.practice",
        "coach.next_action.experiment",
        "coach.next_action.review",
        "coach.next_action.awaiting_evidence",
        "coach.expert_gap.title_zh",
        "coach.expert_gap.title_en",
        "coach.confidence_check.prompt",
        "coach.metacog.title",
        "coach.skill_chain.step",
        "coach.skill_chain.switch_proposed",
        "rubrics.list.title",
        "rubrics.check.dry_run",
    }
)


# Required keys for the expert-coaching-loop P1 milestone (decision /
# practice / evidence-gathering), introduced by Task 3.17.
REQUIRED_P1_KEYS: frozenset[str] = frozenset(
    {
        "decision.predicted_outcome",
        "decision.confidence",
        "decision.verdict.pending",
        "decision.review.title",
        "decision.review.brier",
        "decision.review.log_loss",
        "practice.due.title",
        "practice.cloze",
        "practice.counterexample",
        "practice.socratic",
        "practice.grade.success",
        "practice.grade.partial",
        "practice.grade.fail",
        "evidence.gathering.insufficient",
        "evidence.gathering.searching",
        "evidence.gathering.pending_review",
        "evidence.gathering.approved",
        "evidence.gathering.rejected",
        "evidence.verdict.blocked",
    }
)


# Required keys for the expert-coaching-loop P2 milestone (metacognition
# / analogy / experiment-review), introduced by Task 4.13.
REQUIRED_P2_KEYS: frozenset[str] = frozenset(
    {
        "metacog.questions_title",
        "metacog.confidence_prompt",
        "analogy.title",
        "analogy.cross_domain",
        "analogy.unavailable",
        "experiment.review.title",
        "experiment.review.result_class",
        "experiment.review.metric_breach",
        "experiment.review.chain_switch",
        "experiment.review.human_review",
    }
)


# Required keys for the expert-coaching-loop P3 milestone (learning
# dashboard), introduced by Task 5.7.
REQUIRED_DASHBOARD_KEYS: frozenset[str] = frozenset(
    {
        "dash.title",
        "dash.mastery",
        "dash.calibration",
        "dash.skill_chain",
        "dash.decay",
        "dash.empty",
    }
)


_KEY_LINE_RE = re.compile(r'^\s*"([^"\\]+)"\s*:', re.MULTILINE)


def _extract_dict_block(source: str, decl_prefix: str) -> str:
    """Return the body of the first object literal that follows ``decl_prefix``.

    The body returned excludes the surrounding braces. Brace counting respects
    string literals so ``"}"`` inside a translation value can't unbalance the
    scan.
    """

    start = source.index(decl_prefix)
    open_idx = source.index("{", start)
    depth = 0
    in_string = False
    escape = False
    for i in range(open_idx, len(source)):
        ch = source[i]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return source[open_idx + 1 : i]
    raise AssertionError(f"unbalanced braces after declaration {decl_prefix!r}")


def _keys(block: str) -> set[str]:
    return set(_KEY_LINE_RE.findall(block))


def test_coach_keys_zh_en_parity() -> None:
    assert I18N_FILE.exists(), f"missing {I18N_FILE}"
    text = I18N_FILE.read_text(encoding="utf-8")

    zh_block = _extract_dict_block(text, "const zhCN")
    en_block = _extract_dict_block(text, "const enUS")

    zh_keys = _keys(zh_block)
    en_keys = _keys(en_block)

    only_in_zh = zh_keys - en_keys
    only_in_en = en_keys - zh_keys
    assert not only_in_zh, (
        f"keys present in zhCN but missing from enUS: {sorted(only_in_zh)}"
    )
    assert not only_in_en, (
        f"keys present in enUS but missing from zhCN: {sorted(only_in_en)}"
    )

    missing_zh = REQUIRED_COACH_KEYS - zh_keys
    missing_en = REQUIRED_COACH_KEYS - en_keys
    assert not missing_zh, (
        f"required coach/rubric keys missing from zhCN: {sorted(missing_zh)}"
    )
    assert not missing_en, (
        f"required coach/rubric keys missing from enUS: {sorted(missing_en)}"
    )


def test_p1_keys_zh_en_parity() -> None:
    """The P1 decision/practice/evidence keys exist in both dictionaries."""

    assert I18N_FILE.exists(), f"missing {I18N_FILE}"
    text = I18N_FILE.read_text(encoding="utf-8")

    zh_keys = _keys(_extract_dict_block(text, "const zhCN"))
    en_keys = _keys(_extract_dict_block(text, "const enUS"))

    missing_zh = REQUIRED_P1_KEYS - zh_keys
    missing_en = REQUIRED_P1_KEYS - en_keys
    assert not missing_zh, (
        f"required P1 keys missing from zhCN: {sorted(missing_zh)}"
    )
    assert not missing_en, (
        f"required P1 keys missing from enUS: {sorted(missing_en)}"
    )


def test_p2_keys_zh_en_parity() -> None:
    """The P2 metacognition/analogy/experiment-review keys exist in both."""

    assert I18N_FILE.exists(), f"missing {I18N_FILE}"
    text = I18N_FILE.read_text(encoding="utf-8")

    zh_keys = _keys(_extract_dict_block(text, "const zhCN"))
    en_keys = _keys(_extract_dict_block(text, "const enUS"))

    missing_zh = REQUIRED_P2_KEYS - zh_keys
    missing_en = REQUIRED_P2_KEYS - en_keys
    assert not missing_zh, (
        f"required P2 keys missing from zhCN: {sorted(missing_zh)}"
    )
    assert not missing_en, (
        f"required P2 keys missing from enUS: {sorted(missing_en)}"
    )


def test_dashboard_keys_zh_en_parity() -> None:
    """The learning-dashboard ``dash.*`` keys exist in both dictionaries."""

    assert I18N_FILE.exists(), f"missing {I18N_FILE}"
    text = I18N_FILE.read_text(encoding="utf-8")

    zh_keys = _keys(_extract_dict_block(text, "const zhCN"))
    en_keys = _keys(_extract_dict_block(text, "const enUS"))

    missing_zh = REQUIRED_DASHBOARD_KEYS - zh_keys
    missing_en = REQUIRED_DASHBOARD_KEYS - en_keys
    assert not missing_zh, (
        f"required dashboard keys missing from zhCN: {sorted(missing_zh)}"
    )
    assert not missing_en, (
        f"required dashboard keys missing from enUS: {sorted(missing_en)}"
    )
