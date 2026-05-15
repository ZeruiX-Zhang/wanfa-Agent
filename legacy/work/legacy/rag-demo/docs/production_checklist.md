# 生产化检查清单

该项目当前定位为中文作品集 Demo。若要迁移到生产环境，建议按以下清单补齐。

## 认证与权限

- 配置 `AUTH_ENABLED=true`。
- 使用真实身份提供方替换演示 API Key。
- 从可信 claims 中读取 `tenant_id` 和 `access_roles`。
- 为管理员接口增加更细粒度权限控制。

## RAG 与存储

- 生产共享环境建议使用 PostgreSQL + pgvector。
- 配置 `VECTOR_BACKEND=pgvector` 和 `DATABASE_URL`。
- 执行 `app/db/migrations/001_init_pgvector.sql`。
- 为大规模数据补充索引策略、备份策略和租户隔离测试。

## Agent 安全

- 保持工具白名单。
- 对新增工具补充 Pydantic 参数模型、路径限制和审计日志。
- 禁止将 shell、任意网络访问或敏感文件读取直接暴露给 Agent。

## 可观测性

- 配置 trace 采样率和保留周期。
- 将 `storage/traces/*` 接入集中式日志或对象存储。
- 为 RAG latency、retrieval hit、tool error 增加监控指标。

## 评测与发布

- 发布前运行检索评测和生成评测。
- 关注 `hit_rate`、`mrr`、`average_rank`、citation_coverage。
- 对关键业务域维护 `data/eval/*.jsonl` 回归样本。

## 健康检查

- 部署平台 liveness probe：`GET /health/live`
- 部署平台 readiness probe：`GET /health/ready`
- 浏览器验收：`GET /docs`、`GET /openapi.json`、`GET /demo`

## 配置管理

- 使用 `.env.example` 作为配置参考。
- 不要提交 `.env`。
- OpenAI-compatible API key 只能通过安全环境变量或密钥管理服务注入。
