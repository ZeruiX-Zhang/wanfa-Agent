# Production Readiness

## Safety Checklist

- Tool whitelist: only explicitly allowlisted tools may execute; default is disabled.
- Approval: high-risk actions require human approval before execution.
- API keys: server-only; no API key is exposed to `apps/web` or `apps/extension`.
- Multi-tenant isolation: retrieval and knowledge writes must carry tenant boundaries before real persistence.
- Prompt injection: external webpages/files are untrusted and cannot directly control tools or knowledge writes.
- Trace: retrieval, verification, supervisor, and tool actions must produce redacted trace records.
- Redaction: secrets, tokens, passwords, `.env`, and authorization values are redacted from tool previews.
- Rollback: keep deployment changes small, review diffs, and revert through Git when needed.

## Current Production State

- Ready for local smoke, browser E2E, and human acceptance review.
- Production adapter mode can fail closed instead of silently using mock data.
- API auth can be required through `REALITY_OS_API_AUTH_REQUIRED=true` or `REALITY_OS_ENV=production`.
- Not ready for unattended production execution without a real identity provider, external secret manager, and production database.
- Real connectors still need authentication, tenant enforcement, persistent storage, and approval audit storage.

## Required Before Production

- Replace mock-safe fixtures with reviewed adapters.
- Add persistent DB migrations and rollback migrations.
- Add authenticated API boundaries.
- Replace local SQLite hardening storage with production database migrations.
- Connect production secret manager instead of environment-only status checks.
- Add tenant-scoped retrieval filters.
- Add server-side secret storage.
- Add CI for web build, API smoke, eval smoke, and supervisor policy checks.
