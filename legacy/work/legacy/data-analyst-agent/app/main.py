from __future__ import annotations

from fastapi import FastAPI

from app.api.routes import data_agent_router, public_router


def create_app() -> FastAPI:
    app = FastAPI(
        title="AI 数据分析 Agent 演示系统",
        description=(
            "面向业务分析场景的 Data Analyst Agent，展示 Text-to-SQL、Schema Grounding、"
            "SQL Safety Checker、只读 SQL 执行、图表生成、结构化输出和审计日志。"
        ),
        version="0.1.0",
        openapi_tags=[
            {"name": "公开页面", "description": "健康检查、Demo 页面和图表访问。"},
            {"name": "数据分析 Agent", "description": "Schema、自然语言查询、SQL 校验和 Trace 查询。"},
        ],
    )
    app.include_router(public_router)
    app.include_router(data_agent_router)
    return app


app = create_app()

