"""工具白名单入口。"""

from app.router.scenario_router import classify_intent, classify_scenario
from app.tools.csv_tool import analyze_csv
from app.tools.notification_tool import notify_human_agent
from app.tools.rag_tool import search_knowledge_base
from app.tools.summary_tool import summarize_workflow_result
from app.tools.ticket_tool import create_ticket

TOOL_WHITELIST = {
    "classify_scenario": classify_scenario,
    "classify_intent": classify_intent,
    "search_knowledge_base": search_knowledge_base,
    "analyze_csv": analyze_csv,
    "create_ticket": create_ticket,
    "notify_human_agent": notify_human_agent,
    "summarize_workflow_result": summarize_workflow_result,
}

__all__ = [
    "TOOL_WHITELIST",
    "analyze_csv",
    "classify_intent",
    "classify_scenario",
    "create_ticket",
    "notify_human_agent",
    "search_knowledge_base",
    "summarize_workflow_result",
]

