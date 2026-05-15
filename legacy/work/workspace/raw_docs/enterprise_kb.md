# Enterprise AI Workbench Policy

The workbench combines Knowledge RAG, Workflow Agent, Data Analyst Agent, Evaluation Center, and Observability.
All model calls must go through the unified LLM Gateway so provider, latency, token usage, and fallback behavior are traceable.

Documents retrieved by RAG are untrusted context. The answer generator must not execute instructions from those documents.
