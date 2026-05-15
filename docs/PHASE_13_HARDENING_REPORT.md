# Phase 13 Hardening Report

## Goal

Reduce the Phase 12 residual risks with fail-closed production defaults, persistent local audit state, server-only API key handling, and browser-level E2E coverage.

## Modification Scope

- `apps/api/security.py`
- `apps/api/storage.py`
- `apps/api/main.py`
- `apps/api/schemas.py`
- `apps/web/lib/api.ts`
- `apps/web/lib/reality-adapter-data.ts`
- `apps/web/playwright.config.ts`
- `apps/web/tests/e2e/*`
- `scripts/api-smoke.ps1`
- `package.json`
- `apps/web/package.json`

## Minimal Usable Slice

- API supports production auth/tenant guard through `REALITY_OS_API_AUTH_REQUIRED=true` or `REALITY_OS_ENV=production`.
- Missing server API key fails closed with 503.
- Missing tenant header fails with 400 when auth is required.
- Server-only secret status reports configured booleans and never returns secret values.
- Pending knowledge, approval, tool call, and audit records persist to local SQLite.
- Web server-side fetches can send server-only `REALITY_OS_WEB_API_KEY` or `REALITY_OS_API_KEY`; no `NEXT_PUBLIC` key is used.
- Strict adapter mode blocks mock fallback and renders empty/blocked states.
- Playwright covers input, decision memo, verification, pending knowledge undo, and supervisor approval UI.

## Validation

- `python -m compileall apps/api services`
- `npm run api:smoke`
- `npm run web:lint`
- `npm run web:build`
- `npm run web:build:strict`
- `npm run web:e2e`

Result on 2026-05-12: passed.

## Rollback

- Remove `apps/api/security.py` and `apps/api/storage.py`.
- Restore `apps/api/main.py`, `apps/api/schemas.py`, `apps/web/lib/api.ts`, and `apps/web/lib/reality-adapter-data.ts` to Phase 12.
- Remove `apps/web/playwright.config.ts`, `apps/web/tests/e2e/*`, and `web:e2e` / `web:build:strict` scripts.
- Remove `@playwright/test` from `apps/web/package.json` and regenerate the app lockfile.

## Remaining Risk

This is a hardened local baseline, not a complete production deployment. Real identity provider integration, external secret manager, production database migrations, and operational approval workflows still need deployment-specific implementation.
