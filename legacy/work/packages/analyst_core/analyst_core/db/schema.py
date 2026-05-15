from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Any

from analyst_core.core.config import Settings, get_settings
from analyst_core.db.connection import get_readonly_connection
from analyst_core.schemas.data_agent import ColumnInfo, SchemaInfo, TableSchema


TABLE_DESCRIPTIONS = {
    "orders": "Order fact table with revenue, cost, region, channel, product line, and status.",
    "customers": "Customer dimension table with industry, region, tier, and created date.",
    "tickets": "Support ticket table with category, priority, resolution time, and satisfaction.",
    "marketing_spend": "Marketing spend table with spend, leads, conversions, channel, and region.",
}

FIELD_DESCRIPTIONS = {
    "orders.order_id": "Order ID",
    "orders.order_date": "Order date",
    "orders.region": "Sales region",
    "orders.channel": "Sales or acquisition channel",
    "orders.product_line": "Product line",
    "orders.customer_id": "Customer ID",
    "orders.revenue": "Order revenue",
    "orders.cost": "Order cost",
    "orders.status": "Order status",
    "customers.customer_id": "Customer ID",
    "customers.customer_name": "Customer name",
    "customers.industry": "Customer industry",
    "customers.region": "Customer region",
    "customers.customer_tier": "Customer tier",
    "customers.created_at": "Customer created date",
    "tickets.ticket_id": "Ticket ID",
    "tickets.created_at": "Ticket created date",
    "tickets.customer_id": "Customer ID",
    "tickets.category": "Ticket category",
    "tickets.priority": "Ticket priority",
    "tickets.status": "Ticket status",
    "tickets.resolution_hours": "Resolution time in hours",
    "tickets.satisfaction_score": "Satisfaction score from 1 to 5",
    "marketing_spend.date": "Spend date",
    "marketing_spend.channel": "Marketing channel",
    "marketing_spend.region": "Spend region",
    "marketing_spend.spend": "Spend amount",
    "marketing_spend.leads": "Lead count",
    "marketing_spend.conversions": "Conversion count",
}

IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def quote_identifier(name: str) -> str:
    if not IDENTIFIER_RE.match(name):
        raise ValueError(f"Invalid SQLite identifier: {name}")
    return f'"{name}"'


def _sample_values(conn, table_name: str, column_name: str) -> list[Any]:
    quoted_table = quote_identifier(table_name)
    quoted_col = quote_identifier(column_name)
    rows = conn.execute(
        f"SELECT DISTINCT {quoted_col} AS value FROM {quoted_table} WHERE {quoted_col} IS NOT NULL LIMIT 3"
    ).fetchall()
    return [row["value"] for row in rows]


def retrieve_schema(settings: Settings | None = None) -> SchemaInfo:
    settings = settings or get_settings()
    db_path = settings.database_path
    if not db_path.exists():
        return SchemaInfo(database=str(db_path), generated_at=datetime.now(timezone.utc), tables=[])

    with get_readonly_connection(settings) as conn:
        table_rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ).fetchall()
        tables: list[TableSchema] = []
        for table_row in table_rows:
            table_name = table_row["name"]
            if table_name not in TABLE_DESCRIPTIONS:
                continue
            quoted_table = quote_identifier(table_name)
            count = int(conn.execute(f"SELECT COUNT(*) AS n FROM {quoted_table}").fetchone()["n"])
            column_rows = conn.execute(f"PRAGMA table_info({quoted_table})").fetchall()
            columns = [
                ColumnInfo(
                    name=row["name"],
                    type=row["type"],
                    description=FIELD_DESCRIPTIONS.get(f"{table_name}.{row['name']}", row["name"]),
                    sample_values=_sample_values(conn, table_name, row["name"]),
                )
                for row in column_rows
            ]
            tables.append(
                TableSchema(
                    name=table_name,
                    description=TABLE_DESCRIPTIONS[table_name],
                    row_count=count,
                    columns=columns,
                )
            )
    return SchemaInfo(database=str(db_path), generated_at=datetime.now(timezone.utc), tables=tables)


def schema_table_names(schema_info: SchemaInfo) -> set[str]:
    return {table.name for table in schema_info.tables}
