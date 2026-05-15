# Migration Notes

This integrated repository is designed to be portable and self-contained.

## Desktop Migration Target

- Recommended destination: `D:\UserData\Desktop\work\unified-ai-workflow-platform`

## What Gets Preserved

- The unified production-facing system under `apps/`, `packages/`, `data/`, `storage/`, `scripts/`, and `tests/`
- Frozen snapshots of the original three desktop projects under `legacy/`

## What Is Not Required From Old Desktop Folders

- The new integrated system does not need to import code from:
  - `D:\UserData\Desktop\RAG demo`
  - `D:\UserData\Desktop\multi-scenario-workflow-agent`
  - `D:\UserData\Desktop\data-analyst-agent`

After migration and validation, those original folders can be deleted independently.

## Verification Steps

```powershell
python scripts/init_platform.py
python -m pytest -q
python scripts/verify_self_contained.py
```

Then start the API:

```powershell
$env:API_KEY="test-key"
$env:AUTH_ENABLED="false"
python scripts/run_api.py
```

In another shell:

```powershell
$env:API_KEY="test-key"
python scripts/final_acceptance_check.py
```
