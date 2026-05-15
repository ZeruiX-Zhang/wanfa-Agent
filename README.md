# Reality OS

## Positioning

Reality OS is an interactive AI Agent system designed to elevate beginners to expert-level capability across any domain. It combines a curated knowledge base, multi-source verified search, continuous learning feedback, and Skill-driven hybrid reasoning to provide context-aware guidance: augmenting prompts in the browser, optimizing real-world decisions through chat, and supervising other Agents based on long-term user profiling.

Reality OS is the controlled merge workspace for three existing projects:

- `sou`: Intelligence OS for source collection, search, evidence, compliance, reports, and watchlists.
- `prompt-agent`: Prompt optimization, Prompt Lab, browser extension input, Knowledge OS, review queue, and personal wiki.
- `work`: Enterprise RAG Workbench for RAG pipeline, evaluation, workflow, guardrails, approval, traces, and agent supervision.

This repository is currently through Phase 12 local readiness: unified Web shell, mock-safe adapter surfaces, pending-review knowledge flow, supervisor dry-run shell, smoke acceptance, and production-readiness documentation. The old projects are preserved under `legacy/`; real connector hardening and production persistence are still pending.

## Run the unified stack (quick start)

Prereqs: Python 3.11+ (tested on 3.14), Node.js 20+ / npm 10+.

1. Install web dependencies (first run only):
   ```powershell
   npm --prefix apps/web install
   ```
2. Start the API (keeps legacy routes and adds `/api/*` for the web UI):
   ```powershell
   python -m uvicorn apps.api.main:app --host 127.0.0.1 --port 8000 --reload
   ```
3. In another shell, start the web UI:
   ```powershell
   npm --prefix apps/web run dev
   ```
   The web dev server binds to `0.0.0.0:3010` by default. Visit `http://localhost:3010/dashboard`.
4. Optional env:
   - `NEXT_PUBLIC_API_BASE_URL` (default `http://localhost:8000`)
   - `REALITY_OS_WEB_ORIGINS` (default adds `localhost:3000/3010` to the CORS allow-list)
   - `REALITY_OS_API_KEY` / `REALITY_OS_SERVER_API_KEY` (server-only; auth only enforced when `REALITY_OS_ENV=production` or `REALITY_OS_API_AUTH_REQUIRED=1`)

### What is exposed

The FastAPI app exposes both layers side by side so that:

- The web app's `/api/*` contract (`/api/dashboard`, `/api/sources`, `/api/settings`, `/api/work/supervisor`, etc.) is served by the compat router in `apps/api/app/compat.py`.
- The original routes `/sou/*`, `/prompt/*`, `/work/*`, `/knowledge/*`, `/supervisor/*` remain untouched.
- All writes default to pending review or dry-run (no legacy data is mutated).
- Tool execution is disabled / dry-run; high-risk actions require supervisor approval.

### UI preferences (Settings)

The Settings page (`/settings`) now owns four controls, persisted in a cookie + localStorage so SSR and the client stay in sync:

- **Language** — `zh-CN` (default) or `en`. Instant switch; navigation, top bar, and Settings are translated via `apps/web/lib/i18n.ts`.
- **Palette** — four restrained themes (`Obsidian`, `Pearl`, `Graphite`, `Aurora`) each with a matching dark variant. All palettes are wired through CSS custom properties in `apps/web/app/globals.css` and surfaced by tokens in `apps/web/tailwind.config.ts`, so swapping palettes or toggling Light / Dark only retints; it does not re-render content.
- **Appearance** — Light / Dark toggle. The top bar has a sun/moon shortcut.
- **Mode** — Simple vs Professional.
  - Simple drives the loop with your memory and top-expert defaults — minimal knobs.
  - Professional opens a full parameter panel, grouped as **Thinking & planning**, **Retrieval & evidence**, **Context engineering**, **Quality gate**, **Agent supervision**, **Model & budget**. The parameter catalog lives in `apps/web/lib/professional-parameters.ts` and traces back to requirements.md / design.md so every knob has a grounded reference.

### Verify

```powershell
python -m pytest apps/api/tests -q
npm --prefix apps/web run lint     # tsc --noEmit
npm --prefix apps/web run build
```

Desktop (Tauri) is reserved under `apps/desktop/` and is not built in this iteration.

## Phase 1 Rules

- Do not delete the original projects on `D:\UserData\Desktop`.
- Do not rename large legacy trees.
- Do not copy real `.env` files or API keys.
- Do not write generated AI content directly into a formal knowledge base.
- Do not grant agents unrestricted tool access.
- Treat `legacy/*` as the source of truth until adapters and tests replace each capability.

## Phase 2 Commands

Print all legacy command recipes:

```powershell
npm run legacy:list
```

Run the non-destructive workspace check:

```powershell
npm run doctor
```

Execute one legacy target only when needed:

```powershell
.\scripts\start-legacy.ps1 -Target prompt-backend -Run
```

## Phase 3 Web

Run the unified Web shell:

```powershell
npm run web:dev
```

Check the Web project:

```powershell
npm run web:lint
npm run web:build
```

## Phase 12 Smoke

Run the non-destructive workspace check:

```powershell
npm run doctor
```

Run adapter/API smoke and the Phase 10 acceptance smoke:

```powershell
npm run api:smoke
npm run smoke:phase10
npm run web:e2e
```

## Directory Map

```text
reality-os/
  apps/
    web/
    api/
    desktop/
    extension/
    worker/
  services/
    knowledge/
    retrieval/
    prompt-orchestrator/
    decision/
    verification/
    workflow/
    supervisor/
    reflection/
    evals/
    tool-gateway/
  packages/
    ui/
    types/
    schemas/
    prompts/
    config/
  legacy/
    sou/
    prompt-agent/
    work/
    study/
    prompt-rag-backup/
  docs/
  tests/
  infra/
```

## Current Legacy Locations

| Reality OS path | Original source | Role |
|---|---|---|
| `legacy/sou` | `D:\UserData\Desktop\sou` | Main Web baseline, industry knowledge, search, evidence, compliance |
| `legacy/prompt-agent` | `D:\UserData\Desktop\prompt Agent\prompt-agent` | Prompt clarification, extension, Knowledge OS, reflection |
| `legacy/study` | `D:\UserData\Desktop\prompt Agent\study` | Learning wiki and indexed knowledge source |
| `legacy/prompt-rag-backup` | `D:\UserData\Desktop\prompt Agent\prompt-agent.unrelated-rag-backup-20260507-012027` | Archived RAG reference only |
| `legacy/work` | `D:\UserData\Desktop\work\unified-ai-workflow-platform` | RAG, verification, workflow, supervisor, evals, guardrails |

## Target Architecture

```text
Input -> Clarification -> Retrieval -> Decision Memo -> Verification
      -> Supervisor + Workflow Graph -> Tool Approval -> Reflection
```

The target database is Postgres. Legacy SQLite, Markdown, JSONL, YAML, and workspace artifacts remain readable through adapters until a tested migration exists.

## Documentation

- `docs/LEGACY_INVENTORY.md`: audited legacy capabilities and migration targets.
- `docs/STARTUP_COMMANDS.md`: original startup, build, and test commands.
- `docs/ENVIRONMENT.md`: unified environment variables, port policy, database policy, and safety defaults.
- `docs/PROTECTED_ASSETS.md`: directories and files that must not be deleted casually.
- `docs/PHASE_1_ACCEPTANCE_REPORT.md`: copy and validation result for this phase.
- `docs/PHASE_2_ACCEPTANCE_REPORT.md`: environment and startup command validation result.
- `docs/PHASE_3_ACCEPTANCE_REPORT.md`: unified Web shell and navigation validation result.
- `docs/PHASE_4_ACCEPTANCE_REPORT.md` through `docs/PHASE_12_ACCEPTANCE_REPORT.md`: adapter, memo, knowledge, supervisor, smoke, cleanup, and readiness acceptance.
- `docs/PRODUCTION_READINESS.md`: safety checklist and remaining production gaps.
- `docs/PHASE_13_HARDENING_REPORT.md`: fail-closed auth, tenant guard, secret status, local audit persistence, strict adapter mode, and Playwright E2E validation.
