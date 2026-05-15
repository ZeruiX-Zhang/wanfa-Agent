# Legacy Inventory

Phase 1 preserves existing projects and records migration boundaries. No business logic has been rewritten.

## sou

Role: industry intelligence, source collection, search, evidence, compliance, reports, watchlists.

Technology:

- Backend: Python 3.11+, FastAPI, SQLAlchemy 2, Alembic, Pydantic v2, Uvicorn.
- Frontend: Next.js 15, React 19, TypeScript, Tailwind, TanStack Query, Zustand, Recharts, Lucide.
- Infrastructure: PostgreSQL, Redis, Qdrant, Docker Compose.
- Local default database: SQLite files under `backend/`.

Reusable modules:

- Source registry and compliance.
- Collectors for RSS, search, GitHub, arXiv, markets, products, and custom sources.
- Normalization, extraction, clustering, scoring, verification.
- Evidence ledger and intelligence objects.
- Report generation, jobs, watchlists, product reviews.
- Next.js layout shell, typed API client, and dashboard pages.

Migration targets:

- `apps/web`: use `legacy/sou/frontend` as the Web baseline.
- `services/knowledge`: source, evidence, compliance models.
- `services/retrieval`: search and vector adapters.
- `services/verification`: claim and evidence verification.

Risks:

- Backend port `8000` conflicts with `work`.
- SQLite and Postgres modes must be reconciled.
- Local DB files may contain useful demo state.
- `.deps`, `.tmp`, `.venv`, `.next`, and caches are rebuildable but were copied as legacy context where accessible.

## prompt-agent

Role: prompt clarification, Prompt Lab, browser extension input, Knowledge OS, personal wiki, review queue, reflection.

Technology:

- Backend: FastAPI and Pydantic v2.
- Desktop: Tauri 2 shell with HTML/CSS/JS UI.
- Browser: Chrome Manifest V3 extension.
- Storage: Markdown, JSONL, local settings JSON.

Reusable modules:

- `PromptAgent`, `PromptLabService`, provider factory and presets.
- `KnowledgeOSService`, review queue, graph JSONL, claims, sources.
- Personal wiki service and privacy settings.
- Browser extension capture channel.

Migration targets:

- `apps/extension`: browser extension, simplified as an input collector.
- `services/prompt-orchestrator`: prompt generation and clarification.
- `services/reflection`: Level Up, review queue, personal wiki, learning plan.
- `services/knowledge`: Knowledge OS adapter.

Risks:

- Hardcoded backend URL `http://127.0.0.1:8787`.
- Root path contains a space in the original project.
- Current desktop build setup has Tauri/Vite/React mismatch history.
- Knowledge writes must remain pending-review only.

## study

Role: indexed learning and personal knowledge source.

Technology:

- Markdown/Obsidian-style vault, no app runtime.

Reusable assets:

- `llm-wiki/CLAUDE.md` source-grounded operating rules.
- `llm-wiki/raw/` immutable raw input.
- `llm-wiki/wiki/` structured concepts, claims, maps, sources, questions.
- `schema/AI-RULES.md` and `schema/WORKFLOW.md` learning coach rules.

Migration targets:

- `services/knowledge`: read-only indexed source.
- `services/reflection`: learning workflow and review rules.

Risks:

- `raw/` must not be rewritten.
- AI-generated synthesis must go to pending knowledge, not directly into formal wiki pages.

## work

Role: enterprise RAG, verification, workflow, supervisor, evals, guardrails, tool approvals.

Technology:

- API: FastAPI, Pydantic v2, Uvicorn.
- Desktop: PySide6.
- Data: SQLite, JSON/YAML configs, local workspace artifacts.
- RAG: hybrid retrieval, local vector store, mock/real LLM gateway, eval reports.
- Agent: workflow runtime, tool registry, approvals, traces, guardrails.

Reusable modules:

- `packages/workspace`
- `packages/rag_core`
- `packages/llm_gateway`
- `packages/platform_common`
- `packages/workflow_core`
- `packages/analyst_core`
- `packages/security`
- `packages/guardrails`
- `packages/tool_registry`

Migration targets:

- `services/retrieval`: RAG pipeline and debug.
- `services/verification`: verifier and evidence reporting.
- `services/workflow`: workflow graph/runtime.
- `services/supervisor`: approval, trace, risk routing.
- `services/evals`: evaluation datasets and reports.
- `services/tool-gateway`: safe tool registry.

Risks:

- API port `8000` conflicts with `sou`.
- Runtime artifacts in `workspace/` and `storage/` may be user data, not disposable cache.
- CI/config has port and vector backend inconsistencies that need Phase 2 cleanup.
- PySide6 remains legacy until Web + Tauri reaches parity.

## prompt-rag-backup

Role: archived RAG reference only.

Reusable candidates:

- Document loader, cleaner, chunker.
- FAISS vector store and retriever.
- Prompt builder, domain router, eval runner.
- Tool whitelist patterns and trace middleware.

Migration target:

- No direct runtime target in Phase 1.
- Extract individual ideas only after `work` RAG and `prompt` Knowledge OS adapters are stable.

Risks:

- Real `.env` existed in the source and was excluded.
- Some pytest/tmp directories have restrictive ACLs and were not fully readable.
- Dependencies overlap with `work`; do not merge requirements wholesale.
