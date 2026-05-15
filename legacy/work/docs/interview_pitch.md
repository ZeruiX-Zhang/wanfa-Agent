# 5 Minute Interview Pitch

This project turns three independent AI demos into one Enterprise AI Workbench. It demonstrates how to move from "LLM demo" to an operable product surface: model calls are centralized, data access is safe, retrieval is debuggable, tools are governed, and every run is traceable and evaluable.

The architecture has one FastAPI shell and layered packages. RAG handles document ingestion, hybrid retrieval, rerank fallback, and citations. Workflow Agent routes tasks through a controlled workflow and pauses high-risk actions for confirmation. Data Analyst Agent performs schema-grounded Text-to-SQL with SELECT-only validation and read-only execution.

The main engineering decisions are pragmatic. External providers are optional because mock mode keeps the project runnable in interviews and CI. The vector store is local JSONL for portability, but the retriever interface can be swapped to pgvector or FAISS. Evaluation is deterministic fallback first, with a clear extension point for RAGAS or LLM-as-judge.

The most important hardening is safety and observability: SQL guardrails, prompt-injection boundaries for untrusted context, PII masking, rate limits, tool risk levels, trace IDs, structured logs, and debug APIs. The known limits are also explicit: no full RBAC, SSO, multi-tenant ACL, or distributed queue in this version.
