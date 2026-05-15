# Phase 11 Acceptance Report

## Goal

Clean up duplicate code and mark obsolete old entrypoints without deleting legacy assets.

## Modification Scope

- `docs/DEPRECATED_ENTRYPOINTS.md`
- Phase reports and README references
- Removed only the duplicate new `apps/api/app/*` skeleton generated during Phase 4 convergence.

## Minimal Usable Slice

- Deprecated entrypoints are documented.
- Legacy projects remain untouched.
- Adapter-replaced behaviors are marked in docs instead of deleted from legacy.

## Validation

- `npm run web:lint`
- `npm run web:build`
- `python -m compileall apps/api services`

Result on 2026-05-12: passed.

## Rollback

- Remove `docs/DEPRECATED_ENTRYPOINTS.md`.
- Recreate the deleted duplicate `apps/api/app/*` only if an alternate app package entrypoint is required.

## Stop-on-Failure Rule

If cleanup removes a legacy asset or breaks a covered adapter, stop immediately.
