# Architecture

Enterprise AI Workbench uses one FastAPI shell and layered packages. Business modules call shared infrastructure instead of duplicating model, trace, safety, or config logic.

Core runtime path:

1. `apps/api` receives HTTP requests.
2. `platform_common` resolves auth, settings, trace IDs, events, and rate limits.
3. `rag_core`, `workflow_core`, or `analyst_core` handles the domain workflow.
4. `llm_gateway` owns model provider calls and mock fallback.
5. `storage/` keeps local traces, RAG chunks, SQLite data, tickets, charts, and eval artifacts.

The system is intentionally self-contained for demos: local JSONL vector store, SQLite warehouse, and mock model provider are enough to run tests and demos.
