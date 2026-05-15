from __future__ import annotations

from llm_gateway import ChatMessage, get_gateway
from analyst_core.schemas.data_agent import SQLPlan, SchemaInfo


class OpenAICompatibleClient:
    def __init__(self) -> None:
        self.gateway = get_gateway()

    def generate_sql_plan(self, question: str, schema_info: SchemaInfo) -> SQLPlan | None:
        schema_json = schema_info.model_dump_json()
        prompt = (
            "Return a JSON object matching SQLPlan. Use only known tables and columns. "
            "Only generate SELECT SQL for SQLite.\n\n"
            f"Question: {question}\nSchema: {schema_json}"
        )
        plan, _response = self.gateway.structured_output(
            [
                ChatMessage(role="system", content="You are a schema-grounded read-only SQL planner."),
                ChatMessage(role="user", content=prompt),
            ],
            SQLPlan,
        )
        return plan
