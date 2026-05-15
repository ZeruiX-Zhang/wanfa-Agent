"""Output validators for thinking model results.

Each thinking model declares an output_schema and code_validators in its
SKILL.md frontmatter. This module implements the deterministic validation
logic that ensures model outputs meet structural requirements.

These validators run AFTER the LLM generates output (or after deterministic
generation), and BEFORE the result is returned to the user. They are part
of the L4 acceptance check.
"""

from __future__ import annotations

from typing import Any


def validate_output(
    *,
    model_id: str,
    output: dict[str, Any],
    code_validators: list[dict[str, Any]],
) -> dict[str, Any]:
    """Validate a thinking model's output against its declared validators.

    Returns: {passed: bool, issues: [{validator, message}]}
    """
    issues: list[dict[str, str]] = []

    for validator in code_validators:
        if not isinstance(validator, dict):
            continue
        for rule_name, rule_value in validator.items():
            result = _run_validator(rule_name, rule_value, output, model_id)
            if result:
                issues.append({"validator": rule_name, "message": result})

    return {
        "passed": len(issues) == 0,
        "issues": issues,
    }


def _run_validator(rule_name: str, rule_value: Any, output: dict[str, Any], model_id: str) -> str | None:
    """Run a single validation rule. Returns error message or None if passed."""

    if rule_name == "min_depth" and isinstance(rule_value, (int, str)):
        # For five-whys: check why_chain has minimum depth
        chain = output.get("why_chain", [])
        min_val = int(rule_value)
        if len(chain) < min_val:
            return f"why_chain has {len(chain)} items, minimum is {min_val}"
        return None

    if rule_name == "requires_evidence_markers" and rule_value:
        # Check that output text contains evidence markers (✓ or [?])
        text = str(output)
        if "✓" not in text and "[?]" not in text and "fact" not in text and "hypothesis" not in text:
            return "Output lacks evidence markers (✓ or [?])"
        return None

    if rule_name == "all_fields_non_empty" and rule_value:
        # Check all required fields are non-empty
        for key, val in output.items():
            if isinstance(val, str) and not val.strip():
                return f"Field '{key}' is empty"
            if isinstance(val, list) and len(val) == 0:
                return f"Field '{key}' is an empty list"
        return None

    if rule_name == "min_branches" and isinstance(rule_value, (int, str)):
        branches = output.get("branches", [])
        min_val = int(rule_value)
        if len(branches) < min_val:
            return f"branches has {len(branches)} items, minimum is {min_val}"
        return None

    if rule_name == "max_branches" and isinstance(rule_value, (int, str)):
        branches = output.get("branches", [])
        max_val = int(rule_value)
        if len(branches) > max_val:
            return f"branches has {len(branches)} items, maximum is {max_val}"
        return None

    if rule_name == "min_categories" and isinstance(rule_value, (int, str)):
        categories = output.get("categories", {})
        min_val = int(rule_value)
        if isinstance(categories, dict) and len(categories) < min_val:
            return f"Only {len(categories)} categories, minimum is {min_val}"
        return None

    if rule_name == "min_scenarios" and isinstance(rule_value, (int, str)):
        scenarios = output.get("failure_scenarios", [])
        min_val = int(rule_value)
        if len(scenarios) < min_val:
            return f"Only {len(scenarios)} scenarios, minimum is {min_val}"
        return None

    if rule_name == "items_sorted_descending" and rule_value:
        items = output.get("items", [])
        if len(items) >= 2:
            # Check if items have a numeric field and are sorted
            for item in items:
                if isinstance(item, dict) and "value" in item:
                    values = [float(i.get("value", 0)) for i in items if isinstance(i, dict)]
                    if values != sorted(values, reverse=True):
                        return "Items are not sorted in descending order"
                    break
        return None

    if rule_name == "min_criteria" and isinstance(rule_value, (int, str)):
        criteria = output.get("criteria", [])
        min_val = int(rule_value)
        if len(criteria) < min_val:
            return f"Only {len(criteria)} criteria, minimum is {min_val}"
        return None

    if rule_name == "min_options" and isinstance(rule_value, (int, str)):
        options = output.get("options", [])
        min_val = int(rule_value)
        if len(options) < min_val:
            return f"Only {len(options)} options, minimum is {min_val}"
        return None

    if rule_name == "weights_sum_to_one" and rule_value:
        criteria = output.get("criteria", [])
        if criteria and isinstance(criteria[0], dict):
            weights = [float(c.get("weight", 0)) for c in criteria]
            total = sum(weights)
            if abs(total - 1.0) > 0.05:
                return f"Weights sum to {total:.2f}, should be ~1.0"
        return None

    if rule_name == "has_hypothesis" and rule_value:
        if not output.get("hypothesis"):
            return "Missing hypothesis"
        return None

    if rule_name == "has_metric" and rule_value:
        if not output.get("success_metric") and not output.get("metric"):
            return "Missing success metric"
        return None

    if rule_name == "has_timeline" and rule_value:
        if not output.get("timeline") and not output.get("time_bound"):
            return "Missing timeline"
        return None

    if rule_name == "has_deadline" and rule_value:
        if not output.get("deadline") and not output.get("t_time_bound"):
            return "Missing deadline"
        return None

    if rule_name == "has_failure_signal" and rule_value:
        if not output.get("failure_signal"):
            return "Missing failure signal"
        return None

    if rule_name == "has_baseline" and rule_value:
        plan = output.get("plan", {})
        if isinstance(plan, dict) and not plan.get("baseline"):
            return "Plan section missing baseline"
        return None

    if rule_name == "has_next_action" and rule_value:
        act = output.get("act", {})
        if isinstance(act, dict) and not act.get("next_change"):
            # Also check top-level
            if not output.get("minimum_action") and not output.get("next_action"):
                return "Missing next action"
        return None

    if rule_name == "problem_statement_min_length" and isinstance(rule_value, (int, str)):
        ps = output.get("problem_statement", "")
        min_len = int(rule_value)
        if len(str(ps)) < min_len:
            return f"problem_statement is too short ({len(str(ps))} chars, min {min_len})"
        return None

    if rule_name == "reframed_different_from_surface" and rule_value:
        surface = output.get("surface_statement", "")
        reframed = output.get("reframed_statement", "")
        if surface and reframed and surface.strip() == reframed.strip():
            return "Reframed statement is identical to surface statement"
        return None

    if rule_name == "has_constraints" and rule_value:
        if not output.get("constraints"):
            return "Missing constraints"
        return None

    if rule_name == "has_success_criteria" and rule_value:
        if not output.get("success_criteria"):
            return "Missing success criteria"
        return None

    if rule_name == "has_current_solutions" and rule_value:
        if not output.get("current_solutions"):
            return "Missing current solutions"
        return None

    if rule_name == "all_dimensions_addressed" and rule_value:
        for dim in ("s_specific", "m_measurable", "a_achievable", "r_relevant", "t_time_bound"):
            if not output.get(dim):
                return f"SMART dimension '{dim}' not addressed"
        return None

    if rule_name == "has_target_metric" and rule_value:
        plan = output.get("plan", {})
        if isinstance(plan, dict) and not plan.get("target"):
            return "Plan missing target metric"
        return None

    if rule_name == "each_scenario_has_prevention" and rule_value:
        scenarios = output.get("failure_scenarios", [])
        actions = output.get("prevention_actions", [])
        if scenarios and len(actions) < min(3, len(scenarios)):
            return f"Only {len(actions)} prevention actions for {len(scenarios)} scenarios (need at least {min(3, len(scenarios))})"
        return None

    if rule_name == "has_percentage" and rule_value:
        items = output.get("items", [])
        if items and isinstance(items[0], dict) and "percentage" not in items[0]:
            return "Items missing percentage field"
        return None

    if rule_name == "min_causes_per_category" and isinstance(rule_value, (int, str)):
        categories = output.get("categories", {})
        min_val = int(rule_value)
        if isinstance(categories, dict):
            for cat, causes in categories.items():
                if isinstance(causes, list) and len(causes) < min_val:
                    return f"Category '{cat}' has {len(causes)} causes, minimum is {min_val}"
        return None

    if rule_name == "job_statement_format" and isinstance(rule_value, str):
        js = output.get("job_statement", "")
        # Check if it roughly follows "当...时...以便..." or "When...want...so that..."
        if "当" in str(js) or "When" in str(js) or "want" in str(js).lower():
            return None
        return "job_statement doesn't follow the expected format"

    # Unknown validator — skip silently
    return None
