# Phase 2 Acceptance Report

Date: 2026-05-11

## Scope Completed

- Added a root command catalog in `package.json`.
- Added `scripts/start-legacy.ps1` as a unified legacy command wrapper.
- Added `scripts/check-phase2.ps1` as a non-destructive Phase 2 doctor.
- Added `scripts/README.md`.
- Added `docs/ENVIRONMENT.md`.
- Updated `.env.example` with non-conflicting Reality OS orchestration ports.
- Updated `docs/STARTUP_COMMANDS.md` with Reality OS wrapper usage.

## Port Decisions

| Service | Reality OS default |
|---|---:|
| Unified API | `8010` |
| Unified Web | `3010` |
| Legacy sou backend | `8001` |
| Legacy sou Web | `3001` |
| Legacy prompt-agent backend | `8787` |
| Legacy prompt-agent desktop | `1420` |
| Legacy work API | `8002` |

The legacy projects still retain their original defaults internally. These values are only the Reality OS orchestration defaults.

## Command Decisions

- `npm run doctor` runs the non-destructive Phase 2 check.
- `npm run legacy:list` prints all legacy command recipes.
- `npm run legacy:*` scripts print a single command recipe.
- `scripts/start-legacy.ps1 -Target <target> -Run` executes one target.
- The wrapper refuses to execute `all` at once.

## Acceptance Criteria

- Unified environment vocabulary exists in `.env.example`.
- Startup commands are available from the root.
- Real `.env` files remain ignored and absent from the new workspace.
- Legacy projects remain untouched under `legacy/`.
- No business code migration was performed.

## Verification

Passed:

```powershell
npm run doctor
```

Also passed:

```powershell
.\scripts\start-legacy.ps1 -Target all
```

The second command printed command recipes only; it did not start services.

## Rollback

Phase 2 is additive. Roll back by removing:

- `package.json`
- `scripts/`
- `docs/ENVIRONMENT.md`
- `docs/PHASE_2_ACCEPTANCE_REPORT.md`

Then restore `.env.example` and `docs/STARTUP_COMMANDS.md` from the Phase 1 version if needed.
