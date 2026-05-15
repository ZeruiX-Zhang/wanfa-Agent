# Environment Plan

Reality OS defines a unified environment vocabulary without changing legacy business code.

## Port Policy

Reality OS reserves non-conflicting ports for the unified layer and assigns alternate ports to legacy services when they are launched through `scripts/start-legacy.ps1`.

| Variable | Default | Purpose |
|---|---:|---|
| `REALITY_OS_API_PORT` | `8010` | Future unified FastAPI API |
| `REALITY_OS_WEB_PORT` | `3010` | Future unified Next.js Web |
| `SOU_BACKEND_PORT` | `8001` | Legacy sou FastAPI when launched from Reality OS |
| `SOU_FRONTEND_PORT` | `3001` | Legacy sou Next.js when launched from Reality OS |
| `PROMPT_AGENT_PORT` | `8787` | Legacy prompt-agent FastAPI |
| `PROMPT_AGENT_DESKTOP_PORT` | `1420` | Legacy prompt-agent Tauri dev server |
| `WORK_API_PORT` | `8002` | Legacy work FastAPI when launched from Reality OS |
| `WORK_LEGACY_RAG_PORT` | `8765` | Archived work RAG demo reference |
| `WORK_LEGACY_WORKFLOW_PORT` | `8770` | Archived work workflow reference |
| `WORK_LEGACY_ANALYST_PORT` | `8780` | Archived work analyst reference |

Original legacy defaults are documented in `docs/STARTUP_COMMANDS.md`; the values above are Reality OS orchestration defaults to avoid `8000` and `3000` collisions.

## Database Policy

Postgres is the target system of record:

```text
DATABASE_URL=postgresql+psycopg://reality_os:reality_os@127.0.0.1:5432/reality_os
```

Legacy SQLite, Markdown, JSONL, YAML, and workspace artifacts remain source data until tested adapters or migrations exist.

## Tenant and Permission Policy

Every future unified table must carry tenant scope or be explicitly global:

- `DEFAULT_TENANT_ID`
- `DEFAULT_USER_ID`
- `DEFAULT_ROLES`
- `AUTH_ENABLED`
- `API_KEY`

No retrieval adapter should mix personal, enterprise, industry, and study knowledge without a tenant and visibility filter.

## Secret Policy

- Real `.env` files are ignored by `.gitignore`.
- `.env.example` may contain variable names only.
- API keys must remain server-side.
- Generated AI knowledge must go to pending review before indexing as trusted knowledge.

## Tool Safety Defaults

| Variable | Default | Meaning |
|---|---|---|
| `ALLOW_TOOL_EXECUTION` | `false` | Executor tools are disabled until explicitly enabled |
| `REQUIRE_APPROVAL_FOR_HIGH_RISK` | `true` | High-risk actions need approval |
| `KNOWLEDGE_WRITES_REQUIRE_REVIEW` | `true` | Knowledge writes go to pending review |
| `PROMPT_INJECTION_DETECTION` | `true` | External content is checked as untrusted |
| `REDACT_SENSITIVE_INFO` | `true` | Logs and tool calls should redact sensitive data |
