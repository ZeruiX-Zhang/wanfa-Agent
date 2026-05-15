from __future__ import annotations

import json
import os
import platform
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
import sitecustomize  # noqa: F401


def main() -> int:
    result: dict[str, object] = {
        "cwd": str(Path.cwd()),
        "root_dir": str(ROOT_DIR),
        "python": sys.executable,
        "python_version": sys.version,
        "platform": platform.platform(),
        "platform_root_env": os.getenv("PLATFORM_ROOT"),
    }
    try:
        import PySide6

        result["pyside6"] = str(Path(PySide6.__file__).resolve())
    except Exception as exc:
        result["pyside6_error"] = repr(exc)
    try:
        from workspace.services import services

        result["workspace"] = services.workspace.get_workspace_paths()
        result["documents"] = len(services.documents.list_documents())
        result["chunks"] = len(services.chunking.list_chunks())
    except Exception as exc:
        result["service_error"] = repr(exc)
    try:
        from desktop.main_window import MainWindow  # noqa: F401

        result["desktop_import"] = "ok"
    except Exception as exc:
        result["desktop_import_error"] = repr(exc)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if "desktop_import_error" not in result and "pyside6_error" not in result else 1


if __name__ == "__main__":
    raise SystemExit(main())
