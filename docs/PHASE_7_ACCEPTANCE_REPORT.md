# Phase 7 Acceptance Report

## Goal

Close the judgment memo loop from input to clarification, retrieval, and memo draft.

## Modification Scope

- `apps/web/app/decision/[id]/page.tsx`
- `apps/web/lib/reality-adapter-data.ts`
- `apps/api/schemas.py`
- `apps/api/main.py`

## Minimal Usable Slice

- DecisionCase, ClarifiedProblem, and DecisionMemo schemas exist.
- Memo draft displays recommendation, evidence, counterarguments, risks, confidence, and status.
- No evidence produces an explicit `insufficient evidence` state.

## Validation

- `python -m compileall apps/api services`
- `npm run web:lint`
- `npm run web:build`

Result on 2026-05-12: passed.

## Rollback

- Restore `/decision/[id]` to the Phase 3 shell.
- Remove decision schema and memo draft route additions from `apps/api`.
- Remove decision data helpers from `apps/web/lib/reality-adapter-data.ts`.

## Stop-on-Failure Rule

If memo rendering or schema validation fails, stop before knowledge write work.
