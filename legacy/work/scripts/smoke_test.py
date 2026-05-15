from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
import sitecustomize  # noqa: F401

from analyst_core.agent.pipeline import DataAnalystAgent
from analyst_core.schemas.data_agent import DataAgentQueryRequest
from platform_common.settings import get_settings
from rag_core.rag.service import RequestContext, rag_service
from scripts.init_platform import initialize_platform


def main() -> None:
    init = initialize_platform(reset_traces=False)
    settings = get_settings()
    rag = rag_service.query("What is the enterprise customer P1 response time?", context=RequestContext(tenant_id=settings.default_tenant_id, roles=settings.default_roles))
    data = DataAnalystAgent(enable_trace=False).run(DataAgentQueryRequest(question="Show the 2025 quarterly revenue trend.", include_trace=False))
    result = {
        "init": init,
        "rag_has_answer": bool(rag.get("answer")),
        "rag_citation_count": len(rag.get("citations", [])),
        "data_status": data.status,
        "data_row_count": data.row_count,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["rag_has_answer"] or result["data_status"] != "completed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
