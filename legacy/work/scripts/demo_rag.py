from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
import sitecustomize  # noqa: F401

from rag_core.rag.service import RequestContext, rag_service
from scripts.init_platform import initialize_platform
from platform_common.settings import get_settings


def main() -> None:
    initialize_platform(reset_traces=False)
    settings = get_settings()
    context = RequestContext(tenant_id=settings.default_tenant_id, roles=settings.default_roles)
    questions = json.loads((ROOT_DIR / "data" / "sample_queries" / "rag_queries.json").read_text(encoding="utf-8"))
    for question in questions[:10]:
        result = rag_service.query(question, top_k=5, context=context)
        print(json.dumps({"question": question, "answer": result["answer"], "citations": result.get("citations", [])[:3], "trace_id": result.get("debug", {}).get("trace_id")}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
