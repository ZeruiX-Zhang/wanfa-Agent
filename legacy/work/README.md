# Enterprise RAG Workbench

Enterprise RAG Workbench is a PySide6 desktop workbench for enterprise knowledge-base RAG. It provides a local production-grade product skeleton that can run fully in Demo Mode without API keys, while keeping clear service interfaces for real parsers, LLMs, embedding APIs, rerankers, and vector stores.

## Run

```bash
python -m pip install -r requirements.txt
python scripts/seed_demo_data.py --reset
python scripts/run_desktop.py
```

On Windows you can also double-click:

```text
start_enterprise_rag_workbench.bat
```

Smoke test:

```bash
python scripts/smoke_test_rag.py
```

## Workspace

The desktop app creates and uses:

```text
workspace/raw_docs/              imported source files
workspace/parsed_docs/           parsed JSON and text
workspace/cleaned_docs/          cleaned document text and metadata
workspace/chunks/                chunk JSONL exports
workspace/annotations/           LLM/mock annotation JSON
workspace/vector_store/          local JSON vector index and collection metadata
workspace/traces/                RAG query traces
workspace/reports/               RAG and embedding evaluation reports
workspace/exports/               user exports
workspace/rag_workbench.sqlite   local state database
```

SQLite tables: `documents`, `chunks`, `annotations`, `embeddings`, `traces`, `eval_runs`, and `embedding_model_reports`.

## Desktop Pages

The left navigation contains 12 functional pages:

1. Dashboard: workspace, mode, pipeline status, metrics, recent tasks.
2. Knowledge Documents: import files/folders/sample docs, run pipeline stages, inspect errors.
3. Cleaning Rules: edit `cleaning.yaml`, validate, preview before/after blocks, run cleaning.
4. Chunking Rules: edit `chunking.yaml`, preview chunk metadata and split reasons, run chunking.
5. Chunk Preview: filter/search chunks, view details, edit, disable/enable, merge/split, export.
6. LLM Annotation: generate mock/LLM metadata, edit, approve/reject, export.
7. Indexing: embed chunks, rebuild/delete indexes, check collection compatibility.
8. Embedding Model Center: registry, model editor, connection/dimension test, similarity test, retrieval benchmark, comparison report, score weights.
9. Knowledge QA: ask indexed documents, view answer, citations, hit chunks, trace id and latency.
10. Retrieval Debug: inspect query rewrite, fusion/rerank results, context, answer, citations, token usage.
11. Evaluation Reports: run RAG eval and embedding eval, inspect metrics/failures, export reports.
12. Settings: workspace, Demo/Real Mode, LLM, vector store, config import/export/reset.

No page is a placeholder; each page reads or writes through the local service layer.

## RAG Pipeline

The one-click pipeline is:

```text
parse -> clean -> chunk -> annotate -> embed -> index
```

Each step updates `documents.status`, `current_stage`, timestamps, counts, and error fields. Chunk edits mark embeddings stale. Changing embedding model, dimension, distance metric, or normalization can make a collection incompatible and require rebuilding the index.

## Demo Mode

Demo Mode is the default. It supports:

- sample documents from `data/sample_docs`
- mock parser for text-like files
- mock LLM annotation
- deterministic mock embedding vectors
- local JSON vector store
- SQLite records for documents, chunks, embeddings, traces, and reports
- sample traces and evaluation reports

Mock embedding is marked in the UI and answer text as demo-only; it does not represent real semantic retrieval quality.

## Real Mode

Use Settings and Embedding Model Center to configure:

- external LLM provider, model, `base_url`, and `api_key_env`
- OpenAI-compatible or private embedding API
- vector store collection name and distance metric
- cleaning, chunking, retrieval, annotation, embedding, vector store, and LLM YAML files

The service interfaces are already separated as `WorkspaceService`, `DocumentService`, `ParserService`, `CleaningService`, `ChunkingService`, `AnnotationService`, `EmbeddingModelRegistry`, `IndexingService`, `RetrievalService`, `AnswerService`, `QueryService`, `TraceService`, `EvaluationService`, and `SettingsService`.

## Evaluation Metrics

RAG eval reports include:

- context_precision
- context_recall
- faithfulness
- answer_relevancy
- citation_accuracy
- retrieval_hit_rate
- latency
- cost

Embedding model reports include overall score, grade, retrieval quality, semantic separation, RAG context quality, engineering quality, and model comparison fields such as Recall@5, nDCG@10, MRR@10, Precision@5, latency, cost, storage, and reindex requirement.

## Known Limits

- Demo parser is text-first; production PDF/OCR/layout parsing should be plugged into `ParserService`.
- Demo LLM and embedding are deterministic local mocks.
- Local vector store is JSON for inspectability; production deployments should add FAISS, pgvector, Milvus, or a managed vector DB behind `IndexingService`.
- Reranking is heuristic in Demo Mode.
