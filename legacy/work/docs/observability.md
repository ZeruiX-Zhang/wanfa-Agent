# Observability

Trace and debug artifacts are local and inspectable:

- Unified run trace: `storage/traces/runs.jsonl`
- Request events: `storage/traces/events.jsonl`
- LLM calls: `storage/traces/llm_calls.jsonl`
- RAG traces: `storage/traces/rag/*.json`
- Data Agent traces: `storage/traces/analyst_internal.jsonl`

APIs:

- `GET /api/traces?limit=20`
- `GET /api/traces/{trace_id}`
- `GET /debug`

Each RAG, Agent, Data Agent, and LLM Gateway execution records enough metadata for demo debugging.
