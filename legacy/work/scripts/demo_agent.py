from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
import sitecustomize  # noqa: F401

from platform_common.models import AuthContext, UnifiedRunRequest
from platform_common.traces import UnifiedTraceStore
from scripts.init_platform import initialize_platform
from workflow_core.unified_service import run_unified_agent


def main() -> None:
    initialize_platform(reset_traces=False)
    tasks = json.loads((ROOT_DIR / "data" / "sample_queries" / "agent_tasks.json").read_text(encoding="utf-8"))
    auth = AuthContext(user_id="demo", tenant_id="demo", roles=["employee", "support", "finance", "ops", "analyst"])
    store = UnifiedTraceStore()
    for task in tasks[:5]:
        mode = "hybrid" if "revenue" in task.lower() else "auto"
        response = run_unified_agent(UnifiedRunRequest(user_input=task, mode=mode, max_steps=8), auth, trace_store=store)
        print(json.dumps({"task": task, "status": response.status, "answer": response.final_answer, "tools": [step.name for step in response.tool_steps], "pending": response.pending_action.model_dump() if response.pending_action else None, "trace_id": response.trace_id}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
