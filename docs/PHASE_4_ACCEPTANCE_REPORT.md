# Phase 4 Acceptance Report

## Goal

Connect the sou search knowledge base through a unified adapter surface without modifying or moving `legacy/sou`.

## Modification Scope

- Added `apps/api/main.py` and `apps/api/schemas.py` as the first unified FastAPI skeleton.
- Added `apps/web/lib/reality-adapter-data.ts` for mock-safe adapter projections.
- Added `apps/web/components/adapter-surface.tsx`.
- Updated `/dashboard`, `/knowledge`, and `/search` to show adapter data or explicit empty/insufficient-evidence states.

## Minimal Usable Slice

- Read-only sou adapter routes exist for sources, evidence ledger, intelligence objects, and settings.
- Web pages show sou adapter projections and safety defaults.
- Legacy sou remains independently runnable through existing legacy scripts.

## Validation

- `python -m compileall apps/api`
- `npm run web:lint`
- `npm run web:build`

Result on 2026-05-12: passed.

## Rollback

- Delete `apps/api/main.py` and `apps/api/schemas.py`.
- Delete `apps/web/lib/reality-adapter-data.ts` and `apps/web/components/adapter-surface.tsx`.
- Restore `apps/web/app/dashboard/page.tsx`, `apps/web/app/knowledge/page.tsx`, and `apps/web/app/search/page.tsx` to the Phase 3 shell-only implementation.

## Stop-on-Failure Rule

If any validation command fails, stop later phases and fix Phase 4 first.
