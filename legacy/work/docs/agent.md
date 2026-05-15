# Workflow Agent

The main agent entrypoint now runs a controlled QA Orchestrator for knowledge-first questions:

1. classify scenario and intent
2. analyze the question and risk profile
3. build an auditable QA plan with subquestions and retrieval domains
4. collect RAG evidence with multi-query expansion and domain fallback
5. verify citation coverage, evidence sufficiency, and retrieval guardrails
6. compose a structured answer with `answer_type`, confidence, citations, limitations, and trace metadata

`POST /api/v1/agent/run` returns `qa_plan`, `evidence_report`, and `verification` on supported knowledge workflows. The system keeps Data Analyst Agent calls explicit: structured data analysis runs only when the request mode is `analysis` or `hybrid`.

The runtime enforces `max_steps`. High-risk actions such as ticket creation or human notification still return `waiting_approval` and require confirmation through `/api/agent/runs/{run_id}/confirm`.

Tool metadata lives in `packages/tool_registry`.
