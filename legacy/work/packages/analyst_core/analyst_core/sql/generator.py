from __future__ import annotations

from analyst_core.db.schema import schema_table_names
from analyst_core.llm.client import OpenAICompatibleClient
from analyst_core.schemas.data_agent import SQLPlan, SchemaInfo


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
        if ("quarter" in normalized or "quarterly" in normalized or "trend" in normalized) and ("revenue" in normalized or "sales" in normalized):
            return self._sales_trend(question)
        if "region" in normalized and ("growth" in normalized or "fastest" in normalized) and "orders" in available_tables:
            return self._regional_growth(question)
        if "conversion" in normalized and ("lowest" in normalized or "worst" in normalized):
            return self._channel_conversion(question)
        if "gross margin" in normalized or "profit" in normalized or "profitability" in normalized:
            return self._profitability(question)
        if "p1" in normalized and ("resolution" in normalized or "ticket" in normalized):
            return self._p1_resolution(question)
        if ("product" in normalized or "product line" in normalized) and ("highest" in normalized or "top" in normalized or "revenue" in normalized or "sales" in normalized):
            return self._product_revenue(question)
        if ("latest 30 days" in normalized or "last 30 days" in normalized or "recent 30" in normalized) and ("ticket" in normalized or "complaint" in normalized or "issue" in normalized):
            return self._ticket_category_distribution(question, latest_30_days=True)
        if ("high priority" in normalized or "p1" in normalized or "p2" in normalized) and ("category" in normalized or "type" in normalized or "ticket" in normalized):
            return self._high_priority_ticket_categories(question)
        if ("ticket" in normalized or "support" in normalized or "complaint" in normalized) and ("distribution" in normalized or "category" in normalized or "most" in normalized or "issue" in normalized):
            return self._ticket_category_distribution(question)
        if ("monthly" in normalized or "last month" in normalized or "order trend" in normalized) and ("order" in normalized or "revenue" in normalized or "sales" in normalized):
            return self._monthly_order_trend(question)
        if ("投诉" in question or "工单" in question or "客服问题" in question) and ("最多" in question or "分布" in question or "类型" in question):
            if "高优先级" in question:
                return self._high_priority_ticket_categories(question)
            return self._ticket_category_distribution(question, latest_30_days="30" in question)
        if ("产品" in question or "产品线" in question) and ("销售额" in question or "营收" in question or "收入" in question):
            return self._product_revenue(question)
        if ("订单" in question or "上个月" in question) and ("趋势" in question or "订单" in question):
            return self._monthly_order_trend(question)
        if "satisfaction" in normalized and ("lowest" in normalized or "worst" in normalized):
            return self._lowest_satisfaction(question)
        if ("industry" in normalized or "industries" in normalized) and ("revenue" in normalized or "sales" in normalized):
            return self._industry_revenue(question)
        if "roi" in normalized or "marketing" in normalized:
            return self._marketing_roi(question)
        if "new customer" in normalized or "new customers" in normalized:
            return self._last_month_customers(question)

        if "华东" in question and "产品线" in question and ("收入最高" in question or "营收最高" in question):
            return self._east_china_product_line(question)
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
        return SQLPlan(question=question, analysis_type="sales_trend", tables=["orders"], sql=sql, chart_type="line", explanation="Aggregate 2025 revenue by quarter.")

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
        return SQLPlan(question=question, analysis_type="regional_growth", tables=["orders"], sql=sql, chart_type="bar", explanation="Compare regional revenue growth year over year.")

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
        return SQLPlan(question=question, analysis_type="channel_conversion", tables=["marketing_spend"], sql=sql, chart_type="bar", explanation="Find the lowest-converting marketing channel.")

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
        return SQLPlan(question=question, analysis_type="profitability", tables=["orders"], sql=sql, chart_type="bar", explanation="Rank product lines by gross margin.")

    @staticmethod
    def _product_revenue(question: str) -> SQLPlan:
        sql = """
        SELECT
          product_line,
          ROUND(SUM(revenue), 2) AS total_revenue,
          COUNT(*) AS order_count
        FROM orders
        WHERE status <> 'cancelled'
        GROUP BY product_line
        ORDER BY total_revenue DESC
        """
        return SQLPlan(question=question, analysis_type="profitability", tables=["orders"], sql=sql, chart_type="bar", explanation="Rank product lines by total revenue.")

    @staticmethod
    def _ticket_category_distribution(question: str, latest_30_days: bool = False) -> SQLPlan:
        where_clause = ""
        if latest_30_days:
            where_clause = """
        WHERE created_at >= (
          SELECT date(MAX(created_at), '-30 day') FROM tickets
        )
            """
        sql = f"""
        SELECT
          category,
          COUNT(*) AS ticket_count,
          ROUND(AVG(resolution_hours), 2) AS avg_resolution_hours,
          ROUND(AVG(satisfaction_score), 2) AS avg_satisfaction_score
        FROM tickets
        {where_clause}
        GROUP BY category
        ORDER BY ticket_count DESC
        """
        return SQLPlan(question=question, analysis_type="customer_support", tables=["tickets"], sql=sql, chart_type="pie", explanation="Count support tickets by category.")

    @staticmethod
    def _high_priority_ticket_categories(question: str) -> SQLPlan:
        sql = """
        SELECT
          category,
          COUNT(*) AS ticket_count,
          ROUND(AVG(resolution_hours), 2) AS avg_resolution_hours
        FROM tickets
        WHERE priority IN ('P1', 'P2')
        GROUP BY category
        ORDER BY ticket_count DESC
        """
        return SQLPlan(question=question, analysis_type="customer_support", tables=["tickets"], sql=sql, chart_type="bar", explanation="Count high-priority tickets by category.")

    @staticmethod
    def _monthly_order_trend(question: str) -> SQLPlan:
        sql = """
        SELECT
          strftime('%Y-%m', order_date) AS month,
          COUNT(*) AS order_count,
          ROUND(SUM(revenue), 2) AS total_revenue
        FROM orders
        WHERE status <> 'cancelled'
        GROUP BY month
        ORDER BY month
        """
        return SQLPlan(question=question, analysis_type="sales_trend", tables=["orders"], sql=sql, chart_type="line", explanation="Aggregate order count and revenue by month.")

    @staticmethod
    def _east_china_product_line(question: str) -> SQLPlan:
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
        return SQLPlan(question=question, analysis_type="profitability", tables=["orders"], sql=sql, chart_type="bar", explanation="Find the top East China product line by revenue.")

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
        return SQLPlan(question=question, analysis_type="customer_support", tables=["tickets"], sql=sql, chart_type="none", explanation="Measure average P1 resolution time.")

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
        return SQLPlan(question=question, analysis_type="customer_support", tables=["tickets"], sql=sql, chart_type="bar", explanation="Find the ticket category with the lowest satisfaction.")

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
        return SQLPlan(question=question, analysis_type="profitability", tables=["orders", "customers"], sql=sql, chart_type="bar", explanation="Join orders and customers to rank industries by revenue.")

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
        return SQLPlan(question=question, analysis_type="general_query", tables=["marketing_spend"], sql=sql, chart_type="bar", explanation="Estimate channel ROI using a fixed value per conversion.")

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
        return SQLPlan(question=question, analysis_type="general_query", tables=["customers"], sql=sql, chart_type="bar", explanation="Count new customers in the latest customer month by region.")

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
        return SQLPlan(question=question, analysis_type="general_query", tables=["orders"], sql=sql, chart_type="none", explanation="Return recent order detail rows for general inspection.")
