# 安全设计说明

## API 访问控制

- 演示环境使用 `X-API-Key` 或 Bearer Token。
- `AUTH_ENABLED=true` 时，错误或缺失的 API Key 会被拒绝。
- 认证上下文会生成 `tenant_id` 和 `access_roles`，供 RAG 检索过滤使用。

## RAG 权限过滤

- 文档 chunk 带有 `tenant_id`、`domain`、`doc_type` 和 `access_roles`。
- 检索时会在 service / vector store 层过滤租户、业务域和角色。
- `/rag/debug` 会展示过滤前后候选数量，便于面试讲解权限边界。

## Agent 工具安全

- Agent 只允许白名单工具，例如 `search_knowledge` 和 `read_allowed_file`。
- 工具参数使用 Pydantic 校验。
- 本地文件读取必须通过 path guard。
- `.env` 等敏感文件会被拒绝读取。
- 当前演示版不暴露 shell 执行能力。

## 输出安全

- 文档内容被视为不可信输入。
- RAG 和 Agent 输出会清洗常见 secret、API key 和 `.env` 路径泄漏。
- prompt injection 文本不会获得系统权限或绕过工具白名单。

## 面试可讲点

- RAG 的安全边界不只在 LLM prompt，而是在检索过滤、工具白名单和输出清洗多层实现。
- `tenant_id` 和 `access_roles` 可以映射真实企业 IAM / SSO claims。
- `trace_id` 可用于定位某次问答的检索结果、工具调用和延迟。
