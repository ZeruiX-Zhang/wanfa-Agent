from __future__ import annotations

import json
from typing import Any

from fastapi import FastAPI
from fastapi.openapi.docs import (
    get_redoc_html,
    get_swagger_ui_html,
    get_swagger_ui_oauth2_redirect_html,
)
from fastapi.openapi.utils import get_openapi
from fastapi.responses import HTMLResponse


OPENAPI_INFO = {
    "title": "统一 AI Workflow 平台",
    "summary": "统一入口：知识库问答、工作流编排、结构化分析、评测与审批。",
    "description": (
        "这是一个整合后的统一 API 壳。"
        "它把原来的 RAG demo、多场景 workflow agent 和 data analyst agent "
        "收拢到同一套鉴权、配置、存储、追踪与文档界面下。"
    ),
}

OPENAPI_TAGS = [
    {"name": "系统", "description": "健康检查、就绪检查、演示页等系统入口。"},
    {"name": "知识库问答", "description": "RAG 检索、问答、调试与引用返回。"},
    {"name": "文档入库", "description": "知识库文档上传、本地目录导入和任务查询。"},
    {"name": "RAG 评测", "description": "检索评测、生成评测和策略对比。"},
    {"name": "RAG 智能体", "description": "轻量工具型 RAG Agent 与轨迹查询。"},
    {"name": "统一工作流", "description": "多场景工作流编排、审批和执行结果。"},
    {"name": "数据分析", "description": "结构化数据分析和图表产物。"},
    {"name": "运行追踪", "description": "统一 run trace 查询。"},
    {"name": "系统产物", "description": "图表、导出文件等产物访问。"},
]

TAG_RENAMES = {
    "System": "系统",
    "Artifacts": "系统产物",
    "RAG": "知识库问答",
    "Analysis": "数据分析",
    "Workflow": "统一工作流",
    "Runs": "运行追踪",
    "RAG Agent": "RAG 智能体",
}

SCHEMA_LOCALIZATION: dict[str, dict[str, Any]] = {
    "AuthContext": {
        "title": "鉴权上下文",
        "fields": {
            "user_id": {"title": "用户 ID", "description": "当前请求所属的用户标识。"},
            "tenant_id": {"title": "租户 ID", "description": "当前请求所属的租户标识。"},
            "roles": {"title": "角色列表", "description": "当前请求拥有的角色集合。"},
        },
    },
    "GuardrailDecision": {
        "title": "安全护栏决策",
        "fields": {
            "stage": {"title": "检查阶段", "description": "护栏执行阶段。"},
            "decision": {"title": "决策结果", "description": "允许、阻断或人工复核。"},
            "reason": {"title": "原因", "description": "护栏决策说明。"},
            "policy_ids": {"title": "策略编号", "description": "命中的策略 ID 列表。"},
            "redactions": {"title": "脱敏列表", "description": "被脱敏的敏感字段。"},
        },
    },
    "SourceRef": {
        "title": "引用来源",
        "fields": {
            "title": {"title": "来源标题", "description": "引用片段的标题。"},
            "snippet": {"title": "来源片段", "description": "返回给前端的引用摘要。"},
            "url": {"title": "来源链接", "description": "外部或内部文档链接。"},
            "document_id": {"title": "文档 ID", "description": "知识库文档标识。"},
            "chunk_id": {"title": "分片 ID", "description": "命中的知识分片标识。"},
            "score": {"title": "相关度分数", "description": "检索相关度分数。"},
            "domain": {"title": "业务域", "description": "来源所属的业务域。"},
        },
    },
    "DataArtifact": {
        "title": "数据产物",
        "fields": {
            "kind": {"title": "产物类型", "description": "例如 chart、table、file。"},
            "name": {"title": "产物名称", "description": "面向用户展示的名称。"},
            "url": {"title": "访问链接", "description": "通过 API 暴露的访问地址。"},
            "path": {"title": "本地路径", "description": "服务端本地文件路径。"},
            "preview": {"title": "预览摘要", "description": "用于快速预览的文本。"},
            "metadata": {"title": "附加信息", "description": "图表或文件的元数据。"},
        },
    },
    "PendingAction": {
        "title": "待审批操作",
        "fields": {
            "tool": {"title": "工具名", "description": "待执行写操作对应的工具。"},
            "args": {"title": "工具参数", "description": "审批通过后将执行的参数。"},
            "reason": {"title": "触发原因", "description": "为何需要进入审批。"},
        },
    },
    "RunStep": {
        "title": "运行步骤",
        "fields": {
            "name": {"title": "步骤名称", "description": "执行步骤或工具名称。"},
            "status": {"title": "步骤状态", "description": "步骤执行状态。"},
            "args": {"title": "输入参数", "description": "步骤收到的输入参数。"},
            "result": {"title": "步骤结果", "description": "步骤输出结果。"},
            "error": {"title": "错误信息", "description": "失败时的错误描述。"},
            "started_at": {"title": "开始时间", "description": "步骤开始时间。"},
            "ended_at": {"title": "结束时间", "description": "步骤结束时间。"},
        },
    },
    "UnifiedRunRequest": {
        "title": "统一工作流请求",
        "fields": {
            "user_input": {"title": "用户输入", "description": "用户的自然语言请求。"},
            "scenario": {"title": "场景", "description": "指定业务场景，默认自动识别。"},
            "mode": {"title": "执行模式", "description": "auto、knowledge、analysis 或 hybrid。"},
            "top_k": {"title": "召回数量", "description": "RAG 阶段返回的候选片段数量。"},
            "include_trace": {"title": "返回轨迹", "description": "是否在响应中返回 trace URL。"},
            "max_steps": {"title": "最大步骤数", "description": "统一工作流允许的最大执行步数。"},
        },
    },
    "RagQueryRequest": {
        "title": "RAG 问答请求",
        "fields": {
            "question": {"title": "问题", "description": "待检索和回答的问题。"},
            "domain": {"title": "业务域", "description": "指定知识库域；auto 表示自动路由。"},
            "top_k": {"title": "召回数量", "description": "返回给回答器的候选片段数量。"},
            "include_trace": {"title": "返回轨迹", "description": "是否返回 trace URL。"},
        },
    },
    "RagQueryResponse": {
        "title": "RAG 问答响应",
        "fields": {
            "run_id": {"title": "运行 ID", "description": "统一运行标识。"},
            "trace_id": {"title": "轨迹 ID", "description": "统一轨迹标识。"},
            "answer": {"title": "回答", "description": "最终问答结果。"},
            "sources": {"title": "引用来源", "description": "用于支撑回答的引用片段。"},
            "trace_url": {"title": "轨迹链接", "description": "查询统一运行轨迹的地址。"},
            "safety": {"title": "安全信息", "description": "Guardrails 的检查结果。"},
            "debug": {"title": "调试信息", "description": "RAG 调试细节。"},
        },
    },
    "AnalysisQueryRequest": {
        "title": "数据分析请求",
        "fields": {
            "question": {"title": "分析问题", "description": "要交给结构化分析引擎的问题。"},
            "include_trace": {"title": "返回轨迹", "description": "是否返回统一 trace URL。"},
        },
    },
    "ApprovalRequest": {
        "title": "审批请求",
        "fields": {
            "approved": {"title": "是否批准", "description": "true 表示批准，false 表示拒绝。"},
            "comment": {"title": "审批备注", "description": "审批意见或附加说明。"},
        },
    },
    "ApprovalResponse": {
        "title": "审批响应",
        "fields": {
            "run_id": {"title": "运行 ID"},
            "status": {"title": "运行状态"},
            "approval_executed": {"title": "已执行审批"},
            "pending_action": {"title": "待审批操作"},
            "final_answer": {"title": "最终答复"},
            "trace_url": {"title": "轨迹链接"},
            "ticket_id": {"title": "工单 ID"},
        },
    },
    "UnifiedRunResponse": {
        "title": "统一工作流响应",
        "fields": {
            "run_id": {"title": "运行 ID", "description": "统一运行标识。"},
            "trace_id": {"title": "轨迹 ID", "description": "统一轨迹标识。"},
            "status": {"title": "状态", "description": "本次执行的最终状态。"},
            "scenario": {"title": "场景", "description": "实际命中的业务场景。"},
            "mode": {"title": "执行模式", "description": "实际采用的执行模式。"},
            "final_answer": {"title": "最终答复", "description": "用户可直接展示的结果。"},
            "sources": {"title": "引用来源", "description": "支撑回答的来源列表。"},
            "data_artifacts": {"title": "数据产物", "description": "图表、表格等结构化产物。"},
            "pending_action": {"title": "待审批操作", "description": "需要人工审批的写操作。"},
            "trace_url": {"title": "轨迹链接", "description": "查询统一运行轨迹的地址。"},
            "safety": {"title": "安全信息", "description": "安全与 Guardrails 检查结果。"},
            "tool_steps": {"title": "执行步骤", "description": "统一工作流的步骤明细。"},
        },
    },
    "UnifiedRunTrace": {
        "title": "统一运行轨迹",
        "fields": {
            "run_id": {"title": "运行 ID"},
            "trace_id": {"title": "轨迹 ID"},
            "user_input": {"title": "用户输入"},
            "scenario": {"title": "场景"},
            "mode": {"title": "执行模式"},
            "status": {"title": "状态"},
            "final_answer": {"title": "最终答复"},
            "auth_context": {"title": "鉴权上下文"},
            "sources": {"title": "引用来源"},
            "data_artifacts": {"title": "数据产物"},
            "pending_action": {"title": "待审批操作"},
            "tool_steps": {"title": "执行步骤"},
            "guardrails": {"title": "安全护栏"},
            "safety": {"title": "安全信息"},
            "metadata": {"title": "附加元数据"},
            "created_at": {"title": "创建时间"},
            "updated_at": {"title": "更新时间"},
        },
    },
    "HealthResponse": {
        "title": "健康检查响应",
        "fields": {
            "status": {"title": "状态", "description": "服务健康状态。"},
            "service": {"title": "服务名", "description": "当前服务或子系统名称。"},
            "version": {"title": "版本", "description": "服务版本。"},
            "trace_store": {"title": "轨迹存储", "description": "trace 存储路径。"},
        },
    },
    "RagDebugRequest": {
        "title": "RAG 调试请求",
        "fields": {
            "question": {"title": "问题"},
            "domain": {"title": "业务域"},
            "top_k": {"title": "召回数量"},
        },
    },
    "RagDebugResponse": {
        "title": "RAG 调试响应",
    },
    "RagDocumentUploadRequest": {
        "title": "文档上传请求",
    },
    "RagDocumentUploadResponse": {
        "title": "文档上传响应",
    },
    "RagIngestLocalRequest": {
        "title": "本地目录入库请求",
    },
    "RagIngestionJobResponse": {
        "title": "入库任务响应",
    },
    "RagAgentRunRequest": {
        "title": "RAG 智能体运行请求",
    },
    "RagAgentRunResponse": {
        "title": "RAG 智能体运行响应",
    },
    "RagAgentTraceResponse": {
        "title": "RAG 智能体轨迹",
    },
    "RagEvalCase": {
        "title": "RAG 评测样本",
    },
    "RagEvalRunRequest": {
        "title": "RAG 评测请求",
    },
    "RagEvalRunResponse": {
        "title": "RAG 评测响应",
    },
}

SWAGGER_TEXT_MAP = {
    "Authorize": "鉴权",
    "Authorized": "已鉴权",
    "Available authorizations": "可用鉴权方式",
    "Try it out": "试一下",
    "Execute": "执行",
    "Cancel": "取消",
    "Clear": "清空",
    "Reset": "重置",
    "Close": "关闭",
    "Parameters": "参数",
    "Request body": "请求体",
    "Responses": "响应",
    "Response body": "响应体",
    "Response headers": "响应头",
    "Request URL": "请求地址",
    "Server response": "服务端响应",
    "Example Value": "示例值",
    "Schema": "结构定义",
    "Model": "模型",
    "Value": "值",
    "Description": "说明",
    "Name": "名称",
    "Type": "类型",
    "Default value": "默认值",
    "No parameters": "无参数",
    "No links": "无链接",
    "Links": "链接",
    "Code": "状态码",
    "Details": "详情",
    "Example": "示例",
    "Expand all": "展开全部",
    "Collapse all": "折叠全部",
    "Schemas": "数据模型",
    "Download file": "下载文件",
    "Deprecated": "已弃用",
    "Required": "必填",
}

SWAGGER_ATTRIBUTE_MAP = {
    "Try it out": "试一下",
    "Execute": "执行",
    "Cancel": "取消",
    "Clear": "清空",
    "Reset": "重置",
    "Authorize": "鉴权",
    "Available authorizations": "可用鉴权方式",
    "Search...": "搜索...",
    "Filter by tag": "按标签筛选",
}


def _localize_component_schemas(schema: dict[str, Any]) -> None:
    components = schema.get("components", {})
    schema_components = components.get("schemas", {})
    for schema_name, config in SCHEMA_LOCALIZATION.items():
        target = schema_components.get(schema_name)
        if not target:
            continue
        if title := config.get("title"):
            target["title"] = title
        properties = target.get("properties", {})
        for field_name, field_patch in config.get("fields", {}).items():
            field = properties.get(field_name)
            if not field:
                continue
            field.update(field_patch)


def _localize_operations(schema: dict[str, Any]) -> None:
    for methods in schema.get("paths", {}).values():
        for operation in methods.values():
            tags = operation.get("tags", [])
            operation["tags"] = [TAG_RENAMES.get(tag, tag) for tag in tags]
            for parameter in operation.get("parameters", []):
                name = parameter.get("name")
                if name == "authorization":
                    parameter["description"] = "可选 Bearer Token；若启用 API Key，也可留空。"
                elif name == "x-user-id":
                    parameter["description"] = "当前用户 ID；不传则使用默认演示用户。"
                elif name == "x-tenant-id":
                    parameter["description"] = "当前租户 ID；不传则使用默认演示租户。"
                elif name == "x-roles":
                    parameter["description"] = "当前用户角色，多个角色使用逗号分隔。"


def _localize_security_schemes(schema: dict[str, Any]) -> None:
    schemes = schema.get("components", {}).get("securitySchemes", {})
    api_key = schemes.get("APIKeyHeader")
    if api_key:
        api_key["description"] = "请填写 `X-API-Key`。本地演示默认可使用 `change-me`。"


def build_localized_openapi(app: FastAPI) -> dict[str, Any]:
    if app.openapi_schema:
        return app.openapi_schema

    schema = get_openapi(
        title=OPENAPI_INFO["title"],
        version=app.version,
        summary=OPENAPI_INFO["summary"],
        description=OPENAPI_INFO["description"],
        routes=app.routes,
        tags=OPENAPI_TAGS,
    )
    schema["info"]["title"] = OPENAPI_INFO["title"]
    schema["info"]["summary"] = OPENAPI_INFO["summary"]
    schema["info"]["description"] = OPENAPI_INFO["description"]
    schema["tags"] = OPENAPI_TAGS
    _localize_operations(schema)
    _localize_component_schemas(schema)
    _localize_security_schemes(schema)
    app.openapi_schema = schema
    return schema


def install_localized_openapi(app: FastAPI) -> None:
    app.openapi = lambda: build_localized_openapi(app)


def _swagger_localization_script() -> str:
    text_map = json.dumps(SWAGGER_TEXT_MAP, ensure_ascii=False)
    attr_map = json.dumps(SWAGGER_ATTRIBUTE_MAP, ensure_ascii=False)
    return f"""
<script>
(() => {{
  const textMap = {text_map};
  const attrMap = {attr_map};
  const replaceValue = (value, mapping) => {{
    if (!value) return value;
    const trimmed = value.trim();
    return mapping[trimmed] ? value.replace(trimmed, mapping[trimmed]) : value;
  }};
  const localizeTextNodes = (root) => {{
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    let node;
    while ((node = walker.nextNode())) {{
      node.nodeValue = replaceValue(node.nodeValue, textMap);
    }}
  }};
  const localizeAttributes = (root) => {{
    const elements = root.querySelectorAll('*');
    elements.forEach((element) => {{
      ['placeholder', 'value', 'aria-label', 'title'].forEach((attribute) => {{
        const original = element.getAttribute(attribute);
        const translated = replaceValue(original, attrMap);
        if (original && translated !== original) {{
          element.setAttribute(attribute, translated);
          if (attribute === 'value' && 'value' in element) {{
            element.value = translated;
          }}
        }}
      }});
    }});
  }};
  const localize = () => {{
    localizeTextNodes(document.body);
    localizeAttributes(document.body);
    document.documentElement.lang = 'zh-CN';
    document.title = '统一 AI Workflow 平台 - 中文接口文档';
  }};
  window.addEventListener('load', () => {{
    localize();
    setTimeout(localize, 150);
    setTimeout(localize, 600);
  }});
  const observer = new MutationObserver(() => localize());
  observer.observe(document.documentElement, {{ childList: true, subtree: true }});
}})();
</script>
"""


def localized_swagger_ui_html(app: FastAPI) -> HTMLResponse:
    return get_swagger_ui_html(
        openapi_url=app.openapi_url,
        title="Enterprise AI Workbench API Docs",
        oauth2_redirect_url=app.swagger_ui_oauth2_redirect_url,
        swagger_ui_parameters={
            "defaultModelsExpandDepth": 1,
            "docExpansion": "list",
            "displayRequestDuration": True,
            "persistAuthorization": True,
            "syntaxHighlight.theme": "obsidian",
        },
    )


def localized_redoc_html(app: FastAPI) -> HTMLResponse:
    return get_redoc_html(
        openapi_url=app.openapi_url,
        title="统一 AI Workflow 平台 - ReDoc 文档",
    )


def swagger_oauth_redirect_html() -> HTMLResponse:
    return get_swagger_ui_oauth2_redirect_html()
