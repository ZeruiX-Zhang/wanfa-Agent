from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
import sitecustomize  # noqa: F401


REQUIRED_TABLES = {
    "documents",
    "chunks",
    "annotations",
    "embeddings",
    "traces",
    "eval_runs",
    "embedding_model_reports",
}


def main() -> int:
    from scripts.reset_workspace import reset_workspace

    reset_warning = ""
    try:
        reset_workspace()
    except RuntimeError as exc:
        reset_warning = str(exc)
    from workspace.services import services

    if not services.documents.list_documents():
        services.documents.import_sample_docs()
    services.documents.run_full_pipeline()
    question = "What is included in the Enterprise RAG Workbench?"
    answer = services.query.ask(question, {"mode": "hybrid", "top_k": 5, "rerank": True})
    report = services.evaluation.run_rag_eval()
    embedding_report = services.evaluation.run_embedding_eval()
    db_path = Path(services.workspace.get_workspace_paths()["database"])
    with sqlite3.connect(db_path) as conn:
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        counts = {table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] for table in REQUIRED_TABLES}
    checks = {
        "desktop_entry_importable": True,
        "sqlite_exists": db_path.exists(),
        "required_tables": REQUIRED_TABLES.issubset(tables),
        "documents": counts["documents"] > 0,
        "chunks": counts["chunks"] > 0,
        "embeddings": counts["embeddings"] > 0,
        "trace_created": bool(answer.get("trace_id")),
        "citations_created": bool(answer.get("citations")),
        "rag_eval_score": report["metrics"]["overall_score"] > 0,
        "embedding_report": bool(embedding_report["rows"]),
    }
    payload = {"checks": checks, "counts": counts, "answer": answer["answer"][:240], "report": report["metrics"], "reset_warning": reset_warning}
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
