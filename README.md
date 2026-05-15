# Reality OS

## Positioning

Reality OS is an interactive AI Agent system designed to elevate beginners to expert-level capability across any domain. It combines a curated knowledge base, multi-source verified search, continuous learning feedback, and Skill-driven hybrid reasoning to provide context-aware guidance: augmenting prompts in the browser, optimizing real-world decisions through chat, and supervising other Agents based on long-term user profiling.

Reality OS brings together three existing project lines:

- `sou`: Intelligence OS for source collection, search, evidence, compliance, reports, and watchlists.
- `prompt-agent`: Prompt optimization, Prompt Lab, browser extension input, Knowledge OS, review queue, and personal wiki.
- `work`: Enterprise RAG Workbench for RAG pipeline, evaluation, workflow, guardrails, approval, traces, and agent supervision.

The old projects are preserved under `legacy/`. Real connector hardening, production persistence, and tenant-ready deployment remain the main production work.

## Run The Unified Stack

Prereqs: Python 3.11+ and Node.js 20+ / npm 10+.

1. Install web dependencies:

   ```powershell
   npm --prefix apps/web install
   ```

2. Start the API:

   ```powershell
   py -3 -m uvicorn apps.api.main:app --host 127.0.0.1 --port 8000 --reload
   ```

3. In another shell, start the web UI:

   ```powershell
   npm --prefix apps/web run dev
   ```

   The web dev server binds to `0.0.0.0:3010` by default. Visit `http://localhost:3010/dashboard`.

4. Optional env:

   - `NEXT_PUBLIC_API_BASE_URL` defaults to `http://localhost:8000`
   - `REALITY_OS_WEB_ORIGINS` adds localhost web ports to the CORS allow-list by default
   - `REALITY_OS_API_KEY` / `REALITY_OS_SERVER_API_KEY` are server-only keys

## What Is Exposed

The FastAPI app exposes both layers side by side:

- The web app's `/api/*` contract is served by the compat router in `apps/api/app/compat.py`.
- The original routes `/sou/*`, `/prompt/*`, `/work/*`, `/knowledge/*`, `/supervisor/*` remain available.
- All writes default to pending review or dry-run, so legacy data is not mutated.
- Tool execution is disabled by default; high-risk actions require supervisor approval.

## UI Preferences

The Settings page (`/settings`) owns four controls, persisted in a cookie and localStorage so SSR and the client stay in sync:

- **Language** - `zh-CN` or `en`
- **Palette** - `Obsidian`, `Pearl`, `Graphite`, and `Aurora`, each with a matching dark variant
- **Appearance** - Light / Dark
- **Mode** - Simple vs Professional

Professional mode opens a full parameter panel for thinking and planning, retrieval and evidence, context engineering, quality gates, agent supervision, and model budget.

## Common Commands

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

Run the unified Web shell:

```powershell
npm run web:dev
```

Check the Web project:

```powershell
npm run web:lint
npm run web:build
```

Run API and evaluation smoke checks:

```powershell
npm run api:smoke
npm run smoke:evaluate
npm run web:e2e
```

## Verify

```powershell
py -3 -m pytest apps/api/tests -q
npm --prefix apps/web run lint
npm --prefix apps/web run build
```

Desktop (Tauri) is reserved under `apps/desktop/` and is not built in this iteration.

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

- `docs/LEGACY_INVENTORY.md`: audited legacy capabilities and migration targets
- `docs/STARTUP_COMMANDS.md`: original startup, build, and test commands
- `docs/ENVIRONMENT.md`: unified environment variables, port policy, database policy, and safety defaults
- `docs/PROTECTED_ASSETS.md`: directories and files that must not be deleted casually
- `docs/PRODUCTION_READINESS.md`: safety checklist and remaining production gaps
- `docs/DEPRECATED_ENTRYPOINTS.md`: replaced or wrapper-only legacy entrypoints
