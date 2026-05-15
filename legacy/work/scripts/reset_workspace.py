from __future__ import annotations

import json
import os
import shutil
import sqlite3
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
import sitecustomize  # noqa: F401


def reset_workspace() -> dict[str, str]:
    workspace_root = ROOT_DIR / "workspace"
    db_path = workspace_root / "rag_workbench.sqlite"
    if db_path.exists():
        try:
            with sqlite3.connect(db_path, timeout=0.1) as conn:
                conn.execute("BEGIN EXCLUSIVE")
                conn.rollback()
        except sqlite3.OperationalError as exc:
            raise RuntimeError(
                "workspace/rag_workbench.sqlite is in use. Close Enterprise RAG Workbench or stop scripts\\run_desktop.py / scripts\\run_api.py before resetting."
            ) from exc
        try:
            db_path.unlink()
        except PermissionError as exc:
            raise RuntimeError(
                "workspace/rag_workbench.sqlite is in use. Close Enterprise RAG Workbench or stop scripts\\run_desktop.py / scripts\\run_api.py before resetting."
            ) from exc
    if workspace_root.exists():
        for child in workspace_root.iterdir():
            if child.name == "rag_workbench.sqlite":
                continue
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
    os.environ["RAG_WORKBENCH_SKIP_AUTO_SEED"] = "1"
    from workspace.services import WorkspaceService

    workspace = WorkspaceService()
    return workspace.get_workspace_paths()


def main() -> int:
    paths = reset_workspace()
    print(json.dumps({"reset": True, "workspace": paths}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
