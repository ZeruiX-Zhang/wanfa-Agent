# Phase 1 Acceptance Report

Date: 2026-05-11

## Scope Completed

- Created `D:\UserData\Desktop\reality-os`.
- Created target skeleton: `apps`, `services`, `packages`, `legacy`, `docs`, `tests`, `infra`.
- Copied legacy projects into:
  - `legacy/sou`
  - `legacy/prompt-agent`
  - `legacy/study`
  - `legacy/prompt-rag-backup`
  - `legacy/work`
- Excluded real `.env` files while preserving `.env.example`.
- Wrote root README, `.gitignore`, unified `.env.example`, startup commands, protected asset list, and legacy inventory.

## Copy Summary

| Legacy target | Files copied | Directories present | Notes |
|---|---:|---:|---|
| `legacy/sou` | 36,855 | 5,372 | Main files copied; several pip/pytest temp directories had source ACL denial. |
| `legacy/prompt-agent` | 5,215 | 879 | Copied successfully. |
| `legacy/study` | 99 | 33 | Copied successfully. |
| `legacy/prompt-rag-backup` | 9,696 | 1,074 | Real `.env` files excluded; several pytest/tmp directories had ACL denial. |
| `legacy/work` | 19,401 | 1,775 | Copied successfully. |

## Secret Check

No files named `.env`, `.env.local`, `.env.production`, `.env.development`, or `.env.test` were found under `D:\UserData\Desktop\reality-os` after copying.

Targeted text scan of non-generated legacy source, config, Markdown, extension, and knowledge directories found no obvious real OpenAI/DeepSeek/Qwen API key values.

Known excluded source secrets:

- `D:\UserData\Desktop\prompt Agent\prompt-agent.unrelated-rag-backup-20260507-012027\.env`
- `D:\UserData\Desktop\prompt Agent\prompt-agent.unrelated-rag-backup-20260507-012027\.pytest_tmp\test_summarize_document_reject0\.env`

## ACL Exceptions

These source directories or generated temp trees had access restrictions during copy. They were not treated as business assets, but the exception is recorded because the merge policy requires denied paths to be surfaced.

`sou`:

- `legacy/sou/backend/.tmp/pip-build-tracker-sau6ejih`
- `legacy/sou/backend/.tmp/pip-ephem-wheel-cache-495_o6v6`
- `legacy/sou/backend/.tmp/pip-install-l47b29pk`
- `legacy/sou/backend/.tmp/pip-target-0vciguoy`
- `legacy/sou/backend/pytest-cache-files-mch8jggd`

`prompt-rag-backup`:

- `legacy/prompt-rag-backup/.local/pytest-run-mvp2`
- `legacy/prompt-rag-backup/.local/pytest-tmp`
- `legacy/prompt-rag-backup/.local/tmp-mvp2`
- `legacy/prompt-rag-backup/apps/agent-core/.pytest_tmp_codex_mvp2`
- `legacy/prompt-rag-backup/apps/agent-core/pytest-cache-files-4kk75rwm`
- `legacy/prompt-rag-backup/apps/agent-core/pytest-cache-files-d0by5fm2`
- `legacy/prompt-rag-backup/apps/agent-core/pytest-cache-files-eqjocrav`
- `legacy/prompt-rag-backup/apps/agent-core/pytest-cache-files-h92h5mh_`

## Acceptance Criteria

- Original old project directories were not deleted or moved.
- Legacy folders exist under `reality-os/legacy`.
- Startup commands are documented.
- Protected assets are documented.
- Real `.env` files were not copied.
- No business refactor or API migration was performed.

## Rollback

Phase 1 is additive. Rollback is to remove `D:\UserData\Desktop\reality-os`; the original projects remain at their original paths.

## Not Done In Phase 1

- No dependency installation.
- No unified API implementation.
- No database migration to Postgres.
- No Web UI migration into `apps/web`.
- No adapter implementation.
- No Agent/tool execution integration.
