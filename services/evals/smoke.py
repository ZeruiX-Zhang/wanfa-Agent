"""CLI smoke for eval adapter data."""

from __future__ import annotations

import json

from .adapter import EvalAdapter


def main() -> int:
    """Print smoke acceptance data and return non-zero on failed summary."""

    flow = EvalAdapter().build_smoke_acceptance_data()
    print(json.dumps(flow, indent=2, sort_keys=True))
    summary = flow.get("eval_summary", {})
    if isinstance(summary, dict) and summary.get("passed") is True:
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
