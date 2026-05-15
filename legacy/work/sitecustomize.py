from __future__ import annotations

import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent
PACKAGE_DIRS = (
    ROOT_DIR / "apps",
    ROOT_DIR / "packages" / "common",
    ROOT_DIR / "packages" / "workspace",
    ROOT_DIR / "packages" / "document_pipeline",
    ROOT_DIR / "packages" / "rag_engine",
    ROOT_DIR / "packages" / "cleaning",
    ROOT_DIR / "packages" / "chunking",
    ROOT_DIR / "packages" / "annotation",
    ROOT_DIR / "packages" / "embedding",
    ROOT_DIR / "packages" / "vector_store",
    ROOT_DIR / "packages" / "retrieval",
    ROOT_DIR / "packages" / "reranker",
    ROOT_DIR / "packages" / "observability",
    ROOT_DIR / "packages" / "platform_common",
    ROOT_DIR / "packages" / "guardrails",
    ROOT_DIR / "packages" / "llm_gateway",
    ROOT_DIR / "packages" / "tool_registry",
    ROOT_DIR / "packages" / "evaluation",
    ROOT_DIR / "packages" / "security",
    ROOT_DIR / "packages" / "rag_core",
    ROOT_DIR / "packages" / "workflow_core",
    ROOT_DIR / "packages" / "analyst_core",
)

for package_dir in PACKAGE_DIRS:
    package_dir_str = str(package_dir)
    if package_dir.exists() and package_dir_str not in sys.path:
        sys.path.insert(0, package_dir_str)
