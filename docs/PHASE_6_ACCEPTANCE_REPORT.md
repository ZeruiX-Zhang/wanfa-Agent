# Phase 6 Acceptance Report

## Goal

Connect work verification and eval surfaces without changing the original work RAG pipeline.

## Modification Scope

- `services/verification/*`
- `services/evals/*`
- `apps/web/app/verification/[id]/page.tsx`
- `apps/web/app/search/page.tsx`
- `apps/api/main.py` work adapter routes

## Minimal Usable Slice

- RAG query/debug projections are mock-safe and read-only.
- Verification binds claims to evidence when supplied.
- Missing evidence is marked `insufficient_evidence`.
- Eval summary and trace are visible in the web shell.

## Validation

- `python -m compileall apps/api services`
- `python -m services.evals.smoke`
- `npm run web:lint`
- `npm run web:build`

Result on 2026-05-12: passed.

## Rollback

- Restore `/verification/[id]` and `/search` to shell-only pages.
- Remove `services/verification/*` and `services/evals/*`.
- Remove work verification/eval routes from `apps/api/main.py`.

## Stop-on-Failure Rule

If verification smoke fails, do not use eval output as acceptance evidence.
