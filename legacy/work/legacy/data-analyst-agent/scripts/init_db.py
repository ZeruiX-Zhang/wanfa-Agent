from __future__ import annotations

import argparse
from datetime import date, timedelta
import os
from pathlib import Path
import random
import sqlite3


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATABASE_URL = "sqlite:///data/analyst.db"


REGIONS = ["华东", "华南", "华北", "西南"]
CHANNELS = ["线上商城", "直销", "代理商", "伙伴渠道"]
PRODUCT_LINES = ["数据平台", "AI助手", "自动化工具", "安全审计"]
INDUSTRIES = ["制造业", "零售", "金融", "医疗", "教育", "互联网"]
TIERS = ["战略客户", "大型客户", "成长客户", "普通客户"]
TICKET_CATEGORIES = ["登录问题", "数据导入", "权限配置", "报表异常", "计费咨询"]
MARKETING_CHANNELS = ["线上广告", "内容营销", "直销活动", "伙伴渠道"]


def sqlite_path_from_url(database_url: str) -> Path:
    raw_path = database_url.removeprefix("sqlite:///") if database_url.startswith("sqlite:///") else database_url
    path = Path(raw_path)
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path


def initialize_database(database_path: Path, seed: int = 42) -> dict[str, int]:
    random.seed(seed)
    database_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(database_path) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        drop_tables(conn)
        create_tables(conn)
        customers = generate_customers()
        conn.executemany(
            """
            INSERT INTO customers (customer_id, customer_name, industry, region, customer_tier, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            customers,
        )
        orders = generate_orders(customers)
        conn.executemany(
            """
            INSERT INTO orders (order_id, order_date, region, channel, product_line, customer_id, revenue, cost, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            orders,
        )
        tickets = generate_tickets(customers)
        conn.executemany(
            """
            INSERT INTO tickets (ticket_id, created_at, customer_id, category, priority, status, resolution_hours, satisfaction_score)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            tickets,
        )
        marketing = generate_marketing_spend()
        conn.executemany(
            """
            INSERT INTO marketing_spend (date, channel, region, spend, leads, conversions)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            marketing,
        )
        conn.commit()
        counts = {
            "orders": conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0],
            "customers": conn.execute("SELECT COUNT(*) FROM customers").fetchone()[0],
            "tickets": conn.execute("SELECT COUNT(*) FROM tickets").fetchone()[0],
            "marketing_spend": conn.execute("SELECT COUNT(*) FROM marketing_spend").fetchone()[0],
        }
    return counts


def drop_tables(conn: sqlite3.Connection) -> None:
    for table in ["orders", "tickets", "marketing_spend", "customers"]:
        conn.execute(f"DROP TABLE IF EXISTS {table}")


def create_tables(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE customers (
          customer_id TEXT PRIMARY KEY,
          customer_name TEXT NOT NULL,
          industry TEXT NOT NULL,
          region TEXT NOT NULL,
          customer_tier TEXT NOT NULL,
          created_at TEXT NOT NULL
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
          status TEXT NOT NULL,
          FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
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
          satisfaction_score REAL NOT NULL,
          FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
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
    conn.execute("CREATE INDEX idx_orders_date_region ON orders(order_date, region)")
    conn.execute("CREATE INDEX idx_orders_customer ON orders(customer_id)")
    conn.execute("CREATE INDEX idx_tickets_customer ON tickets(customer_id)")
    conn.execute("CREATE INDEX idx_marketing_channel ON marketing_spend(channel, region)")


def generate_customers() -> list[tuple[str, str, str, str, str, str]]:
    customers: list[tuple[str, str, str, str, str, str]] = []
    start = date(2024, 1, 1)
    for index in range(1, 61):
        created = start + timedelta(days=random.randint(0, 760))
        region = random.choices(REGIONS, weights=[34, 27, 24, 15], k=1)[0]
        industry = random.choice(INDUSTRIES)
        tier = random.choices(TIERS, weights=[10, 24, 38, 28], k=1)[0]
        customers.append(
            (
                f"C{index:04d}",
                f"{region}{industry}客户{index:03d}",
                industry,
                region,
                tier,
                created.isoformat(),
            )
        )
    april_regions = ["华东", "华东", "华南", "华北", "华东", "西南", "华南", "华北", "华东", "华南", "华东", "西南"]
    for offset, region in enumerate(april_regions, start=61):
        created = date(2026, 4, 2) + timedelta(days=offset % 24)
        industry = random.choice(INDUSTRIES)
        customers.append(
            (
                f"C{offset:04d}",
                f"{region}{industry}新客{offset:03d}",
                industry,
                region,
                random.choice(TIERS),
                created.isoformat(),
            )
        )
    return customers


def generate_orders(customers: list[tuple[str, str, str, str, str, str]]) -> list[tuple[str, str, str, str, str, str, float, float, str]]:
    orders: list[tuple[str, str, str, str, str, str, float, float, str]] = []
    customers_by_region = {
        region: [customer for customer in customers if customer[3] == region]
        for region in REGIONS
    }
    region_factor = {
        2024: {"华东": 0.95, "华南": 1.18, "华北": 1.08, "西南": 0.86},
        2025: {"华东": 1.48, "华南": 1.27, "华北": 1.13, "西南": 0.96},
    }
    product_factor = {"数据平台": 1.35, "AI助手": 1.18, "自动化工具": 0.96, "安全审计": 1.08}
    cost_rate = {"数据平台": 0.58, "AI助手": 0.46, "自动化工具": 0.62, "安全审计": 0.52}
    order_index = 1
    for year in [2024, 2025]:
        for month in range(1, 13):
            for _ in range(22):
                region = random.choices(REGIONS, weights=[34, 27, 24, 15], k=1)[0]
                channel = random.choices(CHANNELS, weights=[36, 25, 24, 15], k=1)[0]
                product_line = random.choices(PRODUCT_LINES, weights=[30, 28, 24, 18], k=1)[0]
                customer = random.choice(customers_by_region[region])
                order_day = date(year, month, random.randint(1, 28))
                quarter_lift = 1 + (month - 1) * 0.025 if year == 2025 else 1 + (month - 1) * 0.008
                base = random.uniform(6500, 42000)
                revenue = round(base * region_factor[year][region] * product_factor[product_line] * quarter_lift, 2)
                cost = round(revenue * random.uniform(cost_rate[product_line] - 0.04, cost_rate[product_line] + 0.05), 2)
                status = random.choices(["paid", "shipped", "cancelled"], weights=[78, 17, 5], k=1)[0]
                orders.append(
                    (
                        f"O{order_index:05d}",
                        order_day.isoformat(),
                        region,
                        channel,
                        product_line,
                        customer[0],
                        revenue,
                        cost,
                        status,
                    )
                )
                order_index += 1
    return orders


def generate_tickets(customers: list[tuple[str, str, str, str, str, str]]) -> list[tuple[str, str, str, str, str, str, float, float]]:
    tickets: list[tuple[str, str, str, str, str, str, float, float]] = []
    base_date = date(2025, 1, 1)
    category_satisfaction = {"登录问题": 4.25, "数据导入": 3.75, "权限配置": 4.05, "报表异常": 3.25, "计费咨询": 4.1}
    priority_hours = {"P1": 8, "P2": 22, "P3": 48}
    for index in range(1, 181):
        customer = random.choice(customers)
        category = random.choices(TICKET_CATEGORIES, weights=[18, 25, 20, 24, 13], k=1)[0]
        priority = random.choices(["P1", "P2", "P3"], weights=[18, 42, 40], k=1)[0]
        created = base_date + timedelta(days=random.randint(0, 364))
        resolution = max(1.0, random.gauss(priority_hours[priority], priority_hours[priority] * 0.28))
        satisfaction = min(5.0, max(1.0, random.gauss(category_satisfaction[category], 0.45)))
        status = random.choices(["resolved", "closed", "open"], weights=[70, 24, 6], k=1)[0]
        tickets.append(
            (
                f"T{index:05d}",
                created.isoformat(),
                customer[0],
                category,
                priority,
                status,
                round(resolution, 2),
                round(satisfaction, 2),
            )
        )
    return tickets


def generate_marketing_spend() -> list[tuple[str, str, str, float, int, int]]:
    rows: list[tuple[str, str, str, float, int, int]] = []
    conversion_rate = {"线上广告": 0.105, "内容营销": 0.15, "直销活动": 0.18, "伙伴渠道": 0.072}
    lead_efficiency = {"线上广告": 42, "内容营销": 55, "直销活动": 34, "伙伴渠道": 47}
    start = date(2025, 1, 1)
    for week in range(52):
        current = start + timedelta(days=week * 7)
        for channel in MARKETING_CHANNELS:
            for region in REGIONS:
                spend = round(random.uniform(2800, 15000) * (1.15 if region == "华东" else 1.0), 2)
                leads = max(1, int(spend / random.uniform(lead_efficiency[channel] * 0.8, lead_efficiency[channel] * 1.2)))
                rate = random.uniform(conversion_rate[channel] * 0.82, conversion_rate[channel] * 1.18)
                conversions = max(0, int(leads * rate))
                rows.append((current.isoformat(), channel, region, spend, leads, conversions))
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Initialize SQLite database for data-analyst-agent.")
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL))
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    database_path = sqlite_path_from_url(args.database_url)
    counts = initialize_database(database_path, seed=args.seed)
    print(f"SQLite database initialized: {database_path}")
    for table, count in counts.items():
        print(f"{table}: {count}")


if __name__ == "__main__":
    main()

