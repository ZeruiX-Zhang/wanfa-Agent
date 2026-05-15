# Tasks — Unified Reality OS

> Implementation plan for merging KnowDo + reality-os into one system.
> Authoritative inputs: `./requirements.md`, `./design.md`.
> Scope of this first iteration is **make the existing merged stack runnable**: close the `/api/*` contract gap between `apps/web` and `apps/api`, keep all legacy-safe defaults, and leave production hardening explicit.

## Delivery goals

- App runs: `uvicorn apps.api.main:app` starts; `npm --prefix apps/web run dev` serves the shell.
- Build passes: `npm --prefix apps/web run build`.
- Type-check passes: `npm --prefix apps/web run lint` (this repo wires `lint` to `tsc --noEmit`).
- Backend tests pass: `python -m pytest` green for the API compat layer and existing tests.
- Core flows usable: `/dashboard`, `/sources`, `/input`, `/settings`, `/supervisor`, `/reflection` render without 404s against the unified backend.
- Docs updated: README gets a "Run the unified stack" section.

## Task list

- [x] 1. Create `apps/api/app/compat.py` — a `/api/*` compatibility router that frontend expects.
  - GET `/api/dashboard` — computes `DashboardOverview` over the in-memory fixtures already defined in `apps/api/main.py` (sources / evidence / intelligence objects / pending knowledge).
  - GET `/api/sources` — wraps the existing `/sou/sources` adapter into the `Page<Source>` shape the UI expects.
  - POST `/api/sources`, PATCH `/api/sources/{id}`, DELETE `/api/sources/{id}` — in-memory CRUD against a local store; never mutates legacy data.
  - GET `/api/source-policies` and `/api/sources/{id}/policy` — return empty `Page<SourcePolicy>` or stub policies with safe defaults.
  - GET `/api/compliance-decisions`, POST `/api/sources/{id}/compliance/evaluate` — return an empty page / a mock-safe `needs_review` decision.
  - GET `/api/events`, `/api/events/{id}` — empty page and 404 until an event ingestion path exists.
  - GET `/api/intelligence-objects`, `/api/intelligence-objects/{id}`, POST `/api/intelligence-objects/sync` — wraps the existing SOu adapter.
  - GET `/api/evidence-ledger` — wraps the existing SOu evidence.
  - GET `/api/clusters`, `/api/cross-language-candidates` — empty pages.
  - GET `/api/reports`, `/api/reports/{id}`, POST `/api/reports/generate` — empty page + 404 + a mock-safe preview.
  - GET `/api/watchlists`, `/api/watchlists/{id}` (POST/PATCH/DELETE) — empty page + in-memory CRUD.
  - GET `/api/jobs`, `/api/jobs/{id}`, POST `/api/jobs`, `/api/jobs/{id}/run`, `/api/jobs/run-daily` — deterministic mock-safe jobs.
  - GET `/api/product-reviews`, `/api/product-reviews/{id}`, POST `/api/product-reviews` — empty page + stub detail.
  - GET `/api/settings`, PATCH `/api/settings` — wraps `Settings` with `api_key_status` flags derived from env.
  - POST `/api/prompt/capture` — forwards to the existing `/prompt/capture` capture handler.
  - GET `/api/prompt/capture-summary` — returns the deterministic summary the extension and `input` page already assume.
  - GET `/api/work/supervisor` — projects `SupervisorShell` + existing `/supervisor/snapshot` into the UI shape.

- [x] 2. Wire the compat router and CORS into `apps/api/main.py`.
  - `app.include_router(compat_router)`.
  - Add `CORSMiddleware` with allow-list from env (`REALITY_OS_WEB_ORIGINS`, default `http://localhost:3010,http://127.0.0.1:3010`).
  - Keep `require_api_context` dependency.

- [x] 3. Fix the `Settings` type mismatch.
  - `apps/web/lib/types.ts` adds optional `auth_required` and `tenant_required_in_production` fields so the adapter surface does not trip on the server-security response. (No change needed to frontend callers.)
  - `apps/api/app/compat.py` returns the `Settings` shape the web contract expects.

- [x] 4. Add pytest coverage for the compat router.
  - `apps/api/tests/test_compat.py` with `TestClient` exercising `/api/dashboard`, `/api/sources` CRUD, `/api/settings`, `/api/prompt/capture-summary`, `/api/work/supervisor`, `/api/jobs/run-daily`.
  - Make sure legacy `/sou/*`, `/prompt/*`, `/work/*`, `/knowledge/*`, `/supervisor/*` still pass one smoke test each.

- [x] 5. Update `README.md` with a "Run the unified stack" section.
  - Prereqs, install, `uvicorn apps.api.main:app --reload --port 8000`, `npm --prefix apps/web run dev`, env `NEXT_PUBLIC_API_BASE_URL=http://localhost:8000`.
  - Note: legacy `/sou/*`, `/prompt/*`, `/work/*`, `/knowledge/*`, `/supervisor/*` remain.
  - Note: extension and desktop status.

- [x] 6. Verification.
  - `python -m pytest apps/api/tests -q`.
  - `npm --prefix apps/web run lint` (= `tsc --noEmit`).
  - `npm --prefix apps/web run build`.

- [x] 7. Final change log.
  - Record created/modified files, commands run, verification results, residual risks.

## Out of scope (deferred)

- Full decision/verification/retrieval engines behind `/api/*`. These remain either a) proxied to the stub-safe data already in `main.py` or b) empty-but-well-typed pages. The design document (§5, §6) is the authoritative plan for hardening.
- Auth token store beyond the existing header-based API key.
- Postgres migration; SQLite metadata store stays for v1.
- Desktop (Tauri) packaging; desktop shell is empty in the repo.
