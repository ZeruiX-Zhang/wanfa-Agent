# 截图指南

## 1. `/demo` 首页

- 打开页面：http://127.0.0.1:8765/demo
- 截图重点：中文项目标题、业务域、常用接口入口、演示问题。
- 推荐文件名：`assets/screenshots/demo-home.png`
- 面试中怎么讲：这是给面试官快速理解项目定位的入口页，不需要先读代码。

## 2. `/docs` 中文 Swagger

- 打开页面：http://127.0.0.1:8765/docs
- 截图重点：中文标题、中文 tags、`/rag/query`、`/agent/run`、`/eval/retrieval` 分组。
- 推荐文件名：`assets/screenshots/swagger-cn.png`
- 面试中怎么讲：OpenAPI 已经本地化，接口字段保持英文，描述和示例用中文，方便面试展示。

## 3. `/rag/debug` 请求和返回

- 打开页面：`/docs` 中的 `POST /rag/debug`
- 请求示例：`{"question":"企业客户 P1 响应时间是多少？","domain":"auto","top_k":5}`
- 截图重点：selected_domain、dense_results、bm25_results、reranked_results、sources、trace_id。
- 推荐文件名：`assets/screenshots/rag-debug.png`
- 面试中怎么讲：这张图证明项目不是黑盒问答，可以解释路由、召回、融合和重排。

## 4. `/agent/run` CSV 分析

- 打开页面：`/docs` 中的 `POST /agent/run`
- 请求示例：`{"user_input":"分析 data_analysis 域下 sales_report.csv 的收入均值、最大值和最小值","max_steps":4}`
- 截图重点：selected_tool=`analyze_csv`、column_names、row_count、metrics。
- 推荐文件名：`assets/screenshots/agent-csv.png`
- 面试中怎么讲：Agent 不是只聊天，而是在安全边界内调用结构化工具。

## 5. `/agent/run` 知识库查询

- 请求示例：`{"user_input":"企业客户 P1 响应时间是多少？请查询知识库并给出来源","max_steps":4}`
- 截图重点：selected_tool=`search_knowledge_base`、final_answer、sources 中的 `enterprise_sla.txt`。
- 推荐文件名：`assets/screenshots/agent-kb.png`
- 面试中怎么讲：同一个 Agent 可以根据任务选择知识库工具，并保留来源。

## 6. `/agent/runs/{run_id}` trace

- 打开页面：`/docs` 中的 `GET /agent/runs/{run_id}`
- 截图重点：run_id、trace_id、user_input、selected_tool、tool_args、tool_result、latency_ms。
- 推荐文件名：`assets/screenshots/agent-trace.png`
- 面试中怎么讲：trace 让 Agent 工具调用可回放、可排查、可审计。

## 7. `scripts/final_acceptance_check.py` PASS

- 运行命令：`.\.venv_ok\Scripts\python.exe scripts\final_acceptance_check.py`
- 截图重点：总结果 PASS，每个检查项 PASS，run_id / trace_id。
- 推荐文件名：`assets/screenshots/final-acceptance.png`
- 面试中怎么讲：项目不是只靠口头说明，有一键端到端验收。

## 8. pytest 通过

- 运行命令：`.\.venv_ok\Scripts\python.exe -m pytest -q`
- 截图重点：测试进度和最终通过。
- 推荐文件名：`assets/screenshots/pytest-pass.png`
- 面试中怎么讲：核心逻辑有自动化测试覆盖。

## 9. Git log 提交记录

- 运行命令：`git log --oneline -8`
- 截图重点：OpenAPI 中文化、路由修复、RAG 验收、Agent 验收、包装文档等提交。
- 推荐文件名：`assets/screenshots/git-log.png`
- 面试中怎么讲：项目是按阶段推进的，不是一次性临时拼出来。
