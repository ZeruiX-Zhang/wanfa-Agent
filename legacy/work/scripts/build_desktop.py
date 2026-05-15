from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]


def main() -> int:
    entry = ROOT_DIR / "scripts" / "run_desktop.py"
    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--name",
        "EnterpriseRAGWorkbench",
        "--add-data",
        f"{ROOT_DIR / 'configs'};configs",
        "--add-data",
        f"{ROOT_DIR / 'data'};data",
        str(entry),
    ]
    return subprocess.call(command, cwd=ROOT_DIR)


if __name__ == "__main__":
    raise SystemExit(main())
