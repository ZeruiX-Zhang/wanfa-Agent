# API Examples

## 1. Generate Sample Docs

```bash
python scripts/create_sample_docs.py
```

## 2. Start API

```bash
uvicorn app.main:app --reload --port 8000
```

## 3. Health

```bash
curl http://127.0.0.1:8000/health
```

## 4. Ingest and Build Index

```bash
curl -X POST http://127.0.0.1:8000/documents/ingest-local ^
  -H "Content-Type: application/json" ^
  -d "{\"directory\":\"data/raw\",\"glob_pattern\":\"**/*\",\"build_index\":true}"
```

## 5. RAG Query

```bash
curl -X POST http://127.0.0.1:8000/rag/query ^
  -H "Content-Type: application/json" ^
  -d "{\"question\":\"单次餐饮报销上限是多少？\",\"top_k\":5}"
```

## 6. RAG Debug

```bash
curl -X POST http://127.0.0.1:8000/rag/debug ^
  -H "Content-Type: application/json" ^
  -d "{\"question\":\"公司 API Key 是多少？\",\"top_k\":5}"
```

## 7. Agent Run

```bash
curl -X POST http://127.0.0.1:8000/agent/run ^
  -H "Content-Type: application/json" ^
  -d "{\"user_input\":\"企业客户 P1 SLA 是什么？\",\"max_steps\":4}"
```

## 8. Eval

```bash
curl -X POST http://127.0.0.1:8000/eval/run ^
  -H "Content-Type: application/json" ^
  -d "{\"eval_file\":\"data/eval/rag_eval_questions.jsonl\",\"top_k\":5}"
```
