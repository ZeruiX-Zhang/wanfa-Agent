# 面试演示 Checklist

## 演示前

- 确认当前目录：`D:\UserData\Desktop\RAG demo`
- 检查端口：`netstat -ano | findstr :8765`
- 如端口占用，确认旧进程后再结束：`taskkill /PID <PID> /F`
- 生成 sample docs：`.\.venv_ok\Scripts\python.exe scripts\create_sample_docs.py`
- 跑 pytest：`.\.venv_ok\Scripts\python.exe -m pytest -q`
- 启动服务：`.\.venv_ok\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8765`
- 跑 final acceptance：`.\.venv_ok\Scripts\python.exe scripts\final_acceptance_check.py`
- 打开 `/demo` 和 `/docs`
- 准备截图目录：`assets/screenshots/`

## 演示中

- 先讲业务问题：企业知识库需要来源、权限、可观测性和可验收。
- 展示 `/demo`：说明项目定位和能力清单。
- 展示 `/docs`：说明 API 分层、中文 Swagger 和 schema。
- 演示 `/rag/debug`：展示 Domain Router、Hybrid Retrieval、Reranker、sources。
- 演示 `/agent/run` CSV：展示 `analyze_csv`、列名、行数、收入统计。
- 演示 `/agent/run` 知识库：展示 `search_knowledge_base`、30 分钟 SLA、`enterprise_sla.txt`。
- 演示 `/agent/runs/{run_id}`：展示 selected_tool、tool_args、tool_result、latency。
- 演示 `/eval/retrieval`：展示 hit_rate、MRR、average_rank。
- 强调安全拒绝：`.env` 和 shell 删除请求不会执行。

## 演示后

- 展示 README：项目亮点、架构图、启动命令、截图占位。
- 展示架构图：讲清 API、RAG、Agent、Eval、Trace。
- 展示测试结果：pytest、OpenAPI 中文化、final acceptance。
- 展示下一步优化路线：pgvector、cross-encoder reranker、强 ACL、RAGAS / DeepEval、异步 ingestion。
