# 项目局限性与生产化增强方向

这个项目定位是 production-oriented demo，不是完整生产集群。下面是可以在面试中主动说明的局限性。

## 1. 当前 FAISS 是本地单机索引

局限性：适合本地 demo 和小规模样例，不适合多实例高并发和大规模在线索引。

如何生产化增强：接入 pgvector、Milvus、Qdrant、OpenSearch 等服务化检索后端，增加索引版本管理、增量更新和备份恢复。

## 2. access_roles 主要进入 metadata

局限性：当前已经把 tenant_id 和 access_roles 放进 chunk metadata 并参与过滤，但还不是完整企业 IAM / ACL 系统。

如何生产化增强：接入组织架构、用户组、文档权限同步、审计日志和权限变更后的索引刷新。

## 3. Simple reranker 不是工业级 cross-encoder reranker

局限性：当前 reranker 用于展示 rerank 层的工程位置和接口，不等价于高质量语义排序模型。

如何生产化增强：接入 bge-reranker、cross-encoder、商业 reranker 或 LLM reranker，并做离线 eval 和线上 A/B。

## 4. Agent 是规则 + workflow-style

局限性：它不是完全自主 Agent，也不做复杂 planning。

如何生产化增强：保留 workflow-style 的可控性，在明确场景里加入 planner、tool policy、approval gate 和 human-in-the-loop。

## 5. Eval 是轻量 JSONL

局限性：当前 eval 覆盖 hit_rate、MRR、average_rank 和 expected_source，不是完整 RAGAS / DeepEval 体系。

如何生产化增强：增加 answer faithfulness、context precision、human review、回归基线和 CI 中的 eval 阈值。

## 6. 当前 sample docs 是模拟数据

局限性：样例文档用于展示能力，不代表真实企业知识库规模和复杂度。

如何生产化增强：接入真实文档源，如 Confluence、Notion、SharePoint、工单系统和对象存储，并做清洗、去重和权限同步。

## 7. 没有做大规模并发压测

局限性：当前验收重点是功能闭环，不是性能压测报告。

如何生产化增强：加入 locust / k6 压测、缓存、连接池、异步任务队列、批量 embedding 和服务资源监控。

## 8. 没有完整前端后台管理系统

局限性：当前主要通过 `/demo` 和 Swagger 展示，不是完整运营后台。

如何生产化增强：增加文档导入后台、评测面板、trace 浏览器、权限管理和检索调参界面。
