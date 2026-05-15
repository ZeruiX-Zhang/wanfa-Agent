from __future__ import annotations

from apps.worker.tasks import run_ingestion_task


def main() -> None:
    run_ingestion_task()


if __name__ == "__main__":
    main()
