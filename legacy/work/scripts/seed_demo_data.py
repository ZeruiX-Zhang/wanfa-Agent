from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
import sitecustomize  # noqa: F401


def initialize_database(database_path: Path, seed: int = 42) -> dict[str, int]:
    """Compatibility seed for the legacy Data Analyst demo database."""
    del seed
    database_path.parent.mkdir(parents=True, exist_ok=True)
    import sqlite3

    with sqlite3.connect(database_path) as conn:
        for table in ["orders", "tickets", "marketing_spend", "customers"]:
            conn.execute(f"DROP TABLE IF EXISTS {table}")
        conn.execute(
            """
            CREATE TABLE customers (
              customer_id TEXT PRIMARY KEY,
              customer_name TEXT NOT NULL,
              industry TEXT NOT NULL,
              region TEXT NOT NULL,
              customer_tier TEXT NOT NULL,
              created_at TEXT NOT NULL,
              email TEXT,
              phone TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE orders (
              order_id TEXT PRIMARY KEY,
              order_date TEXT NOT NULL,
              region TEXT NOT NULL,
              channel TEXT NOT NULL,
              product_line TEXT NOT NULL,
              customer_id TEXT NOT NULL,
              revenue REAL NOT NULL,
              cost REAL NOT NULL,
              status TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE tickets (
              ticket_id TEXT PRIMARY KEY,
              created_at TEXT NOT NULL,
              customer_id TEXT NOT NULL,
              category TEXT NOT NULL,
              priority TEXT NOT NULL,
              status TEXT NOT NULL,
              resolution_hours REAL NOT NULL,
              satisfaction_score REAL NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE marketing_spend (
              date TEXT NOT NULL,
              channel TEXT NOT NULL,
              region TEXT NOT NULL,
              spend REAL NOT NULL,
              leads INTEGER NOT NULL,
              conversions INTEGER NOT NULL
            )
            """
        )
        customers = [
            ("C0001", "East Finance Customer", "Finance", "East", "Enterprise", "2025-01-10", "user1@example.com", "+1-555-0101"),
            ("C0002", "West Retail Customer", "Retail", "West", "Growth", "2025-02-12", "user2@example.com", "+1-555-0102"),
            ("C0003", "North Healthcare Customer", "Healthcare", "North", "Strategic", "2025-03-15", "user3@example.com", "+1-555-0103"),
        ]
        conn.executemany("INSERT INTO customers VALUES (?, ?, ?, ?, ?, ?, ?, ?)", customers)
        orders = [
            ("O0001", "2025-04-01", "East", "Online", "AI Assistant", "C0001", 42000.0, 21000.0, "paid"),
            ("O0002", "2025-04-03", "West", "Partner", "Data Platform", "C0002", 36000.0, 19000.0, "shipped"),
            ("O0003", "2025-04-05", "North", "Direct", "Security", "C0003", 52000.0, 26000.0, "paid"),
        ]
        conn.executemany("INSERT INTO orders VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", orders)
        tickets = [
            ("T0001", "2025-05-01", "C0001", "Login", "P1", "resolved", 6.0, 4.8),
            ("T0002", "2025-05-02", "C0002", "Data Import", "P2", "open", 18.5, 4.1),
            ("T0003", "2025-05-03", "C0003", "Report", "P3", "closed", 28.0, 4.5),
        ]
        conn.executemany("INSERT INTO tickets VALUES (?, ?, ?, ?, ?, ?, ?, ?)", tickets)
        marketing = [
            ("2025-05-01", "Online", "East", 12000.0, 210, 31),
            ("2025-05-01", "Partner", "West", 9000.0, 150, 18),
            ("2025-05-01", "Direct", "North", 7000.0, 85, 12),
        ]
        conn.executemany("INSERT INTO marketing_spend VALUES (?, ?, ?, ?, ?, ?)", marketing)
        conn.commit()
        return {
            "customers": len(customers),
            "orders": len(orders),
            "tickets": len(tickets),
            "marketing_spend": len(marketing),
        }


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed Enterprise RAG Workbench demo data into workspace/rag_workbench.sqlite.")
    parser.add_argument("--reset", action="store_true", help="Reset the RAG workspace before seeding.")
    args = parser.parse_args()
    reset_warning = ""
    if args.reset:
        from scripts.reset_workspace import reset_workspace

        try:
            reset_workspace()
        except RuntimeError as exc:
            reset_warning = str(exc)
    from workspace.services import services

    imported = services.documents.import_sample_docs()
    doc_ids = [row["doc_id"] for row in imported] or [row["doc_id"] for row in services.documents.list_documents()]
    pipeline = services.documents.run_full_pipeline(doc_ids)
    qa = services.query.ask("What is included in the Enterprise RAG Workbench?", {"mode": "hybrid", "top_k": 5, "rerank": True})
    rag_eval = services.evaluation.run_rag_eval()
    embedding_eval = services.evaluation.run_embedding_eval()
    payload = {
        "workspace": services.workspace.get_workspace_paths(),
        "imported_documents": len(imported),
        "pipeline": pipeline,
        "qa_trace_id": qa.get("trace_id"),
        "rag_eval_score": rag_eval["metrics"]["overall_score"],
        "embedding_models": len(embedding_eval["rows"]),
        "sqlite": services.workspace.get_workspace_paths()["database"],
        "reset_warning": reset_warning,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
