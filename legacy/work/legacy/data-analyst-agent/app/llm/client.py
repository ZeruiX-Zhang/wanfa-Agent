from __future__ import annotations

import json
import urllib.error
import urllib.request

from app.core.config import Settings, get_settings
from app.schemas.data_agent import SQLPlan, SchemaInfo


class OpenAICompatibleClient:
    """Minimal OpenAI-compatible client using JSON Schema structured output."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()

    def generate_sql_plan(self, question: str, schema_info: SchemaInfo) -> SQLPlan | None:
        if not self.settings.llm_enabled:
            return None

        endpoint = self.settings.llm_base_url.rstrip("/") + "/chat/completions"
        schema_text = self._format_schema(schema_info)
        system_prompt = (
            "你是只读数据分析 SQL 规划器。只能使用给定 schema 中存在的表和字段。"
            "只能生成 SELECT SQL，不要生成 DDL/DML，不要访问文件或系统表。"
            "必须返回符合 JSON Schema 的 SQLPlan。"
        )
        body = {
            "model": self.settings.llm_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": f"业务问题：{question}\n\n可用 schema：\n{schema_text}",
                },
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "SQLPlan",
                    "strict": True,
                    "schema": SQLPlan.model_json_schema(),
                },
            },
            "temperature": 0,
        }
        request = urllib.request.Request(
            endpoint,
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.settings.llm_api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                payload = json.loads(response.read().decode("utf-8"))
            content = payload["choices"][0]["message"]["content"]
            return SQLPlan.model_validate_json(content)
        except (KeyError, ValueError, urllib.error.URLError, TimeoutError):
            return None

    @staticmethod
    def _format_schema(schema_info: SchemaInfo) -> str:
        lines: list[str] = []
        for table in schema_info.tables:
            columns = ", ".join(f"{column.name} {column.type}" for column in table.columns)
            lines.append(f"- {table.name}: {columns}")
        return "\n".join(lines)

