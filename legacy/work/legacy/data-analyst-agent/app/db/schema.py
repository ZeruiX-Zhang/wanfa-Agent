from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Any

from app.core.config import Settings, get_settings
from app.db.connection import get_readonly_connection
from app.schemas.data_agent import ColumnInfo, SchemaInfo, TableSchema


TABLE_DESCRIPTIONS = {
    "orders": "订单事实表，记录收入、成本、区域、渠道、产品线和订单状态。",
    "customers": "客户维度表，记录客户行业、区域、客户等级和创建时间。",
    "tickets": "客服工单表，记录问题类型、优先级、状态、解决时长和满意度。",
    "marketing_spend": "市场投放表，记录渠道、区域、花费、线索数和转化数。",
}


FIELD_DESCRIPTIONS = {
    "orders.order_id": "订单 ID",
    "orders.order_date": "订单日期",
    "orders.region": "销售区域",
    "orders.channel": "获客或销售渠道",
    "orders.product_line": "产品线",
    "orders.customer_id": "客户 ID",
    "orders.revenue": "订单收入",
    "orders.cost": "订单成本",
    "orders.status": "订单状态",
    "customers.customer_id": "客户 ID",
    "customers.customer_name": "客户名称",
    "customers.industry": "客户行业",
    "customers.region": "客户所在区域",
    "customers.customer_tier": "客户等级",
    "customers.created_at": "客户创建日期",
    "tickets.ticket_id": "工单 ID",
    "tickets.created_at": "工单创建时间",
    "tickets.customer_id": "客户 ID",
    "tickets.category": "问题类别",
    "tickets.priority": "工单优先级",
    "tickets.status": "工单状态",
    "tickets.resolution_hours": "解决时长，单位小时",
    "tickets.satisfaction_score": "客户满意度评分，1 到 5",
    "marketing_spend.date": "投放日期",
    "marketing_spend.channel": "投放渠道",
    "marketing_spend.region": "投放区域",
    "marketing_spend.spend": "投放花费",
    "marketing_spend.leads": "线索数",
    "marketing_spend.conversions": "转化数",
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

