# Phase 10 Acceptance Report

## Goal

Add a minimal smoke acceptance flow covering the full Reality OS judgment loop.

## Modification Scope

- `services/evals/adapter.py`
- `services/evals/smoke.py`
- `package.json` smoke script

## Minimal Usable Slice

The smoke flow covers:

1. User input
2. Clarification
3. Retrieval
4. Memo
5. Claim
6. Evidence
7. Confidence
8. Pending knowledge policy
9. Agent task
10. Supervisor approval policy

## Validation

- `python -m services.evals.smoke` passed with score `1.0`.
- `npm run smoke:phase10` should run the same smoke path.

Result on 2026-05-12: passed.

## Rollback

- Remove `services/evals/adapter.py` and `services/evals/smoke.py`.
- Remove `smoke:phase10` from `package.json`.

## Stop-on-Failure Rule

If smoke score is not passing, do not claim Phase 10 acceptance.
