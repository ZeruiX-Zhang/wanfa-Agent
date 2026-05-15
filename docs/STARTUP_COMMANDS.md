# Startup Commands

These commands document the legacy projects exactly as Phase 1 found them and the Phase 2 Reality OS command wrappers.

## Reality OS Wrappers

Print all legacy commands:

```powershell
cd D:\UserData\Desktop\reality-os
.\scripts\start-legacy.ps1 -Target all
```

Run the Phase 2 doctor:

```powershell
cd D:\UserData\Desktop\reality-os
.\scripts\check-phase2.ps1
```

Run the current Phase 12 doctor and smoke checks:

```powershell
cd D:\UserData\Desktop\reality-os
npm run doctor
npm run api:smoke
npm run smoke:phase10
npm run web:e2e
```

The wrapper prints commands by default. To execute one target:

```powershell
cd D:\UserData\Desktop\reality-os
.\scripts\start-legacy.ps1 -Target prompt-backend -Run
```

`-Target all -Run` is intentionally rejected to avoid starting multiple legacy servers at once.

## sou

Backend:

```powershell
cd D:\UserData\Desktop\reality-os\legacy\sou\backend
$env:PYTHONPATH='.deps'
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe scripts\seed.py
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Frontend:

```powershell
cd D:\UserData\Desktop\reality-os\legacy\sou\frontend
npm.cmd run dev
npm.cmd run build
npm.cmd run lint
```

Makefile targets: `make dev`, `make backend`, `make frontend`, `make migrate`, `make seed`, `make test`, `make lint`, `make format`, `make build`.

Docker:

```powershell
cd D:\UserData\Desktop\reality-os\legacy\sou
docker compose up --build
```

## prompt-agent

Backend:

```powershell
cd "D:\UserData\Desktop\reality-os\legacy\prompt-agent"
python -m uvicorn app.main:app --host 127.0.0.1 --port 8787
```

Desktop:

```powershell
cd "D:\UserData\Desktop\reality-os\legacy\prompt-agent"
npm.cmd run tauri:dev
npm.cmd run build
```

Tests:

```powershell
cd "D:\UserData\Desktop\reality-os\legacy\prompt-agent"
python -m pytest
```

## work

Setup and demo:

```powershell
cd D:\UserData\Desktop\reality-os\legacy\work
python -m pip install -r requirements.txt
python scripts/seed_demo_data.py --reset
python scripts/run_desktop.py
```

API:

```powershell
cd D:\UserData\Desktop\reality-os\legacy\work
python scripts/init_platform.py
python scripts/run_api.py
```

Tests and smoke:

```powershell
cd D:\UserData\Desktop\reality-os\legacy\work
python -m pytest -q
python scripts/smoke_test_rag.py
python scripts/final_acceptance_check.py
```

Makefile targets: `make setup`, `make dev`, `make seed`, `make ingest`, `make eval`, `make test`, `make demo`, `make smoke`, `make desktop`, `make build-desktop`, `make smoke-test-rag`, `make docker`.

## study

No runtime command. This is a Markdown/Obsidian knowledge and learning workflow source.

## prompt-rag-backup

Archived reference only. Do not expose as a production API.

```powershell
cd D:\UserData\Desktop\reality-os\legacy\prompt-rag-backup
python -m venv .venv
pip install -r requirements.txt
python scripts/create_sample_docs.py
uvicorn app.main:app --reload --port 8000
```
