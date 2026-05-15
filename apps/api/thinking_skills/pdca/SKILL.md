---
name: pdca
description: Use the PDCA loop (Plan, Do, Check, Act) to drive continuous improvement.
metadata:
  category: execution
  version: "1.0"
  author: reality-os
  visual_template: templates/cycle-progress.html
  label_en: PDCA Cycle
  intent_signals:
    - improve
    - iterate
    - optimize
    - cycle
    - continuous
  applicable_when:
    - A process, product, or workflow needs repeated improvement.
    - A previous iteration has completed and needs review.
    - The user needs a structured improvement loop.
  not_applicable_when:
    - There is no baseline yet.
    - The task is a one-time decision.
  output_schema:
    type: object
    required:
      - current_step
      - plan
      - do
      - check
      - act
    properties:
      current_step: {type: string}
      plan: {type: object}
      do: {type: object}
      check: {type: object}
      act: {type: object}
  quality_checks:
    - Plan includes a baseline, hypothesis, metric, and target.
    - Check compares actual results against baseline and target.
    - Act defines a concrete next action.
  code_validators:
    - has_baseline: true
    - has_target_metric: true
    - has_next_action: true
---

## Reasoning Instructions

Use the PDCA loop to help the user make measurable improvement.

### Plan

- Define the current baseline.
- Define the target metric.
- State the improvement hypothesis.
- Decide how success will be measured.

### Do

- Execute the smallest useful change.
- Record what actually happened.
- Capture unexpected side effects.

### Check

- Compare results against the baseline and target.
- Decide whether the hypothesis was supported.
- Identify any tradeoffs or unintended effects.

### Act

- Standardize the change if it worked.
- Adjust the hypothesis if it did not work.
- Define the next improvement loop.
