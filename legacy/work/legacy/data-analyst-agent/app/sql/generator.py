from __future__ import annotations

from app.db.schema import schema_table_names
from app.llm.client import OpenAICompatibleClient
from app.schemas.data_agent import SQLPlan, SchemaInfo


class SQLPlanGenerator:
    def __init__(self, llm_client: OpenAICompatibleClient | None = None):
        self.llm_client = llm_client or OpenAICompatibleClient()
        self.fallback = RuleBasedSQLPlanner()

    def generate(self, question: str, schema_info: SchemaInfo) -> SQLPlan:
        llm_plan = self.llm_client.generate_sql_plan(question, schema_info)
        if llm_plan and self._uses_known_tables(llm_plan, schema_info):
            return llm_plan
        return self.fallback.generate(question, schema_info)

    @staticmethod
    def _uses_known_tables(plan: SQLPlan, schema_info: SchemaInfo) -> bool:
        known_tables = schema_table_names(schema_info)
        return bool(plan.tables) and set(plan.tables).issubset(known_tables)


class RuleBasedSQLPlanner:
    def generate(self, question: str, schema_info: SchemaInfo) -> SQLPlan:
        normalized = question.lower()
        available_tables = schema_table_names(schema_info)

        if "华东" in question and "产品线" in question and ("收入最高" in question or "营收最高" in question):
            return self._huadong_product_line(question)
        if "季度" in question and ("营收" in question or "收入" in question or "趋势" in question):
            return self._sales_trend(question)
        if "区域" in question and ("增长" in question or "最快" in question) and "orders" in available_tables:
            return self._regional_growth(question)
        if "渠道" in question and ("转化率" in question or "转化" in question) and ("最低" in question or "最差" in question):
            return self._channel_conversion(question)
        if "毛利" in question or "利润" in question:
            return self._profitability(question)
        if "p1" in normalized and ("解决" in question or "工单" in question):
            return self._p1_resolution(question)
        if "满意度" in question and ("最低" in question or "最差" in question):
            return self._lowest_satisfaction(question)
        if "行业" in question and ("收入" in question or "营收" in question or "贡献" in question):
            return self._industry_revenue(question)
        if "roi" in normalized or "投放" in question:
            return self._marketing_roi(question)
        if "新增客户" in question or ("上个月" in question and "客户" in question):
            return self._last_month_customers(question)
        return self._general_query(question)

    @staticmethod
    def _sales_trend(question: str) -> SQLPlan:
        sql = """
        SELECT
          printf('Q%d', CAST((CAST(strftime('%m', order_date) AS INTEGER) + 2) / 3 AS INTEGER)) AS quarter,
          ROUND(SUM(revenue), 2) AS total_revenue,
          ROUND(SUM(revenue - cost), 2) AS gross_profit,
          ROUND((SUM(revenue) - SUM(cost)) * 1.0 / NULLIF(SUM(revenue), 0), 4) AS gross_margin
        FROM orders
        WHERE order_date >= '2025-01-01'
          AND order_date < '2026-01-01'
          AND status <> 'cancelled'
        GROUP BY quarter
        ORDER BY quarter
        """
        return SQLPlan(
            question=question,
            analysis_type="sales_trend",
            tables=["orders"],
            sql=sql,
            chart_type="line",
            explanation="按 2025 年季度聚合 orders 表中的收入、毛利和毛利率。",
        )

    @staticmethod
    def _regional_growth(question: str) -> SQLPlan:
        sql = """
        SELECT
          region,
          ROUND(SUM(CASE WHEN order_date >= '2024-01-01' AND order_date < '2025-01-01' THEN revenue ELSE 0 END), 2) AS revenue_2024,
          ROUND(SUM(CASE WHEN order_date >= '2025-01-01' AND order_date < '2026-01-01' THEN revenue ELSE 0 END), 2) AS revenue_2025,
          ROUND(
            (
              SUM(CASE WHEN order_date >= '2025-01-01' AND order_date < '2026-01-01' THEN revenue ELSE 0 END)
              - SUM(CASE WHEN order_date >= '2024-01-01' AND order_date < '2025-01-01' THEN revenue ELSE 0 END)
            ) * 1.0 / NULLIF(SUM(CASE WHEN order_date >= '2024-01-01' AND order_date < '2025-01-01' THEN revenue ELSE 0 END), 0),
            4
          ) AS growth_rate
        FROM orders
        WHERE status <> 'cancelled'
        GROUP BY region
        ORDER BY growth_rate DESC
        """
        return SQLPlan(
            question=question,
            analysis_type="regional_growth",
            tables=["orders"],
            sql=sql,
            chart_type="bar",
            explanation="按 region 聚合 2024 和 2025 年收入，计算同比增长率并降序排序。",
        )

    @staticmethod
    def _channel_conversion(question: str) -> SQLPlan:
        sql = """
        SELECT
          channel,
          SUM(leads) AS leads,
          SUM(conversions) AS conversions,
          ROUND(SUM(conversions) * 1.0 / NULLIF(SUM(leads), 0), 4) AS conversion_rate
        FROM marketing_spend
        GROUP BY channel
        ORDER BY conversion_rate ASC
        """
        return SQLPlan(
            question=question,
            analysis_type="channel_conversion",
            tables=["marketing_spend"],
            sql=sql,
            chart_type="bar",
            explanation="基于 marketing_spend 按渠道计算 conversions / leads 转化率，并找出最低渠道。",
        )

    @staticmethod
    def _profitability(question: str) -> SQLPlan:
        sql = """
        SELECT
          product_line,
          ROUND(SUM(revenue), 2) AS total_revenue,
          ROUND(SUM(revenue - cost), 2) AS gross_profit,
          ROUND((SUM(revenue) - SUM(cost)) * 1.0 / NULLIF(SUM(revenue), 0), 4) AS gross_margin
        FROM orders
        WHERE status <> 'cancelled'
        GROUP BY product_line
        ORDER BY gross_margin DESC
        """
        return SQLPlan(
            question=question,
            analysis_type="profitability",
            tables=["orders"],
            sql=sql,
            chart_type="bar",
            explanation="按产品线聚合收入和成本，计算毛利率排名。",
        )

    @staticmethod
    def _huadong_product_line(question: str) -> SQLPlan:
        sql = """
        SELECT
          product_line,
          ROUND(SUM(revenue), 2) AS total_revenue
        FROM orders
        WHERE region = '华东'
          AND status <> 'cancelled'
        GROUP BY product_line
        ORDER BY total_revenue DESC
        """
        return SQLPlan(
            question=question,
            analysis_type="profitability",
            tables=["orders"],
            sql=sql,
            chart_type="bar",
            explanation="筛选华东地区订单，按产品线聚合收入并排序。",
        )

    @staticmethod
    def _p1_resolution(question: str) -> SQLPlan:
        sql = """
        SELECT
          priority,
          ROUND(AVG(resolution_hours), 2) AS avg_resolution_hours,
          COUNT(*) AS ticket_count
        FROM tickets
        WHERE priority = 'P1'
        GROUP BY priority
        """
        return SQLPlan(
            question=question,
            analysis_type="customer_support",
            tables=["tickets"],
            sql=sql,
            chart_type="none",
            explanation="筛选 P1 工单，计算平均解决时长。",
        )

    @staticmethod
    def _lowest_satisfaction(question: str) -> SQLPlan:
        sql = """
        SELECT
          category,
          ROUND(AVG(satisfaction_score), 2) AS avg_satisfaction_score,
          COUNT(*) AS ticket_count
        FROM tickets
        GROUP BY category
        ORDER BY avg_satisfaction_score ASC
        """
        return SQLPlan(
            question=question,
            analysis_type="customer_support",
            tables=["tickets"],
            sql=sql,
            chart_type="bar",
            explanation="按工单类别聚合满意度，找出平均满意度最低的问题类型。",
        )

    @staticmethod
    def _industry_revenue(question: str) -> SQLPlan:
        sql = """
        SELECT
          c.industry,
          ROUND(SUM(o.revenue), 2) AS total_revenue,
          COUNT(DISTINCT o.customer_id) AS customer_count
        FROM orders o
        JOIN customers c ON c.customer_id = o.customer_id
        WHERE o.status <> 'cancelled'
        GROUP BY c.industry
        ORDER BY total_revenue DESC
        """
        return SQLPlan(
            question=question,
            analysis_type="profitability",
            tables=["orders", "customers"],
            sql=sql,
            chart_type="bar",
            explanation="连接 orders 和 customers，按行业统计客户贡献收入。",
        )

    @staticmethod
    def _marketing_roi(question: str) -> SQLPlan:
        sql = """
        SELECT
          channel,
          ROUND(SUM(spend), 2) AS total_spend,
          SUM(conversions) AS conversions,
          ROUND((SUM(conversions) * 800.0 - SUM(spend)) * 1.0 / NULLIF(SUM(spend), 0), 4) AS roi
        FROM marketing_spend
        GROUP BY channel
        ORDER BY roi DESC
        """
        return SQLPlan(
            question=question,
            analysis_type="general_query",
            tables=["marketing_spend"],
            sql=sql,
            chart_type="bar",
            explanation="按每个转化 800 元估算投放回报，按渠道计算 ROI。",
        )

    @staticmethod
    def _last_month_customers(question: str) -> SQLPlan:
        sql = """
        SELECT
          region,
          COUNT(*) AS new_customers
        FROM customers
        WHERE strftime('%Y-%m', created_at) = (
          SELECT strftime('%Y-%m', MAX(created_at)) FROM customers
        )
        GROUP BY region
        ORDER BY new_customers DESC
        """
        return SQLPlan(
            question=question,
            analysis_type="general_query",
            tables=["customers"],
            sql=sql,
            chart_type="bar",
            explanation="使用 customers 表中最新月份模拟“上个月”，按区域统计新增客户。",
        )

    @staticmethod
    def _general_query(question: str) -> SQLPlan:
        sql = """
        SELECT
          order_date,
          region,
          channel,
          product_line,
          revenue,
          cost,
          status
        FROM orders
        ORDER BY order_date DESC
        """
        return SQLPlan(
            question=question,
            analysis_type="general_query",
            tables=["orders"],
            sql=sql,
            chart_type="none",
            explanation="无法匹配到专门模板时，返回最近订单明细用于人工继续分析。",
        )

