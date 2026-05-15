from __future__ import annotations

import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
import sitecustomize  # noqa: F401

from scripts.demo_agent import main as demo_agent
from scripts.demo_data_agent import main as demo_data_agent
from scripts.demo_rag import main as demo_rag


def main() -> None:
    print("=== RAG Demo ===")
    demo_rag()
    print("=== Agent Demo ===")
    demo_agent()
    print("=== Data Agent Demo ===")
    demo_data_agent()


if __name__ == "__main__":
    main()
