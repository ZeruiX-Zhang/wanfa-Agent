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
from scripts.init_platform import initialize_platform


def main() -> None:
    initialize_platform(reset_traces=False)
    questions = json.loads((ROOT_DIR / "data" / "sample_queries" / "data_agent_queries.json").read_text(encoding="utf-8"))
    agent = DataAnalystAgent(enable_trace=True)
    for question in questions[:10]:
        response = agent.run(DataAgentQueryRequest(question=question, include_trace=True))
        print(json.dumps({"question": question, "status": response.status, "sql": response.sql, "rows": response.table_rows[:3], "answer": response.final_answer, "trace_id": response.trace_id}, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
