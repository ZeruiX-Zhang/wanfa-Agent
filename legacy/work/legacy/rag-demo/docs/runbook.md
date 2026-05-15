# 本地运行 Runbook

## 启动服务

```powershell
.\.venv_ok\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8765
```

浏览器打开：

- Swagger UI：http://127.0.0.1:8765/docs
- ReDoc：http://127.0.0.1:8765/redoc
- 中文演示首页：http://127.0.0.1:8765/demo

## 生成样例数据

```powershell
.\.venv_ok\Scripts\python.exe scripts\create_sample_docs.py
```

样例文档位于 `data/raw/*`，评测样本位于 `data/eval/*.jsonl`。

## 导入知识库

在 Swagger UI 中调用 `POST /documents/ingest-local?sync=true`，示例 body：

```json
{
  "domain": "customer_support",
  "directory": "data/raw/customer_support",
  "glob_pattern": "**/*",
  "build_index": true
}
```

## 常用检查

```powershell
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8765/health
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8765/docs
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8765/openapi.json
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8765/demo
```

## 观测文件

- RAG trace：`storage/traces/rag/`
- Agent trace：`storage/traces/agent/`
- Eval runs：`storage/eval_runs/`

## Docker

```powershell
docker compose up --build api
docker compose --profile pgvector up --build
```
