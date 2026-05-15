from __future__ import annotations

from fastapi import FastAPI

from app.api.routes import router


app = FastAPI(
    title="多业务场景 Workflow Agent 演示系统",
    description=(
        "面向企业客服、金融投研和内部运维的 Workflow Agent 演示系统。"
        "项目展示 Scenario Router、Structured Outputs、工具白名单、Human Approval、安全边界和 Trace。"
    ),
    version="0.1.0",
    openapi_tags=[
        {"name": "健康检查", "description": "服务健康状态。"},
        {"name": "Workflow Agent", "description": "执行多业务 workflow agent。"},
        {"name": "Human Approval", "description": "审批并执行写操作。"},
        {"name": "Trace", "description": "查询工具轨迹和运行记录。"},
        {"name": "工单与通知", "description": "查询 mock 工单、incident 和通知记录。"},
        {"name": "Demo 页面", "description": "中文项目说明页面。"},
    ],
)

app.include_router(router)

