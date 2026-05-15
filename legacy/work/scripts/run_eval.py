from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
import sitecustomize  # noqa: F401

from evaluation.runner import run_evaluation, write_reports
from scripts.init_platform import initialize_platform


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Enterprise AI Workbench evaluation.")
    parser.add_argument("--target", choices=["rag", "agent", "data-agent", "all"], default="all")
    args = parser.parse_args()
    initialize_platform(reset_traces=False)
    report = run_evaluation(args.target)
    write_reports(report)
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
