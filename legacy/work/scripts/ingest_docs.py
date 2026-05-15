from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
import sitecustomize  # noqa: F401

from platform_common.settings import get_settings
from rag_core.rag.ingestion import load_local_documents
from rag_core.rag.service import rag_service


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest local documents into the RAG store.")
    parser.add_argument("--path", default="data/sample_docs")
    parser.add_argument("--domain", default=None)
    parser.add_argument("--glob", default="**/*")
    parser.add_argument("--replace", action="store_true")
    args = parser.parse_args()
    settings = get_settings()
    chunks = load_local_documents(args.path, settings.default_tenant_id, settings.default_roles, domain=args.domain, glob_pattern=args.glob)
    stats = rag_service.ingest_chunks(chunks, replace=args.replace)
    print(json.dumps(stats, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
