from __future__ import annotations

from scripts.init_platform import initialize_platform


def run_ingestion_task() -> dict[str, int]:
    return initialize_platform(reset_traces=False)
