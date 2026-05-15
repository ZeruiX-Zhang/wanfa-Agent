from __future__ import annotations

import os
import sys
import traceback
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
import sitecustomize  # noqa: F401


def main() -> int:
    os.environ.setdefault("PLATFORM_ROOT", str(ROOT_DIR))
    os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")
    try:
        from desktop.main import main as desktop_main
    except ModuleNotFoundError as exc:
        if exc.name == "PySide6":
            print("PySide6 is not installed. Run: python -m pip install -r requirements.txt", file=sys.stderr)
            return 1
        raise
    try:
        return desktop_main()
    except Exception:
        log_path = ROOT_DIR / "tmp-desktop-error.log"
        log_path.write_text(traceback.format_exc(), encoding="utf-8")
        print(f"Desktop startup failed. Details written to {log_path}", file=sys.stderr)
        raise


if __name__ == "__main__":
    raise SystemExit(main())
