from __future__ import annotations

from typing import Any

from analyst_core.schemas.data_agent import SQLPlan


def _pct(value: Any) -> str:
    try:
        return f"{float(value) * 100:.1f}%"
    except (TypeError, ValueError):
        return "N/A"


def _money(value: Any) -> str:
    try:
        return f"{float(value):,.0f}"
    except (TypeError, ValueError):
        return str(value)


class ResultAnalyzer:
    def analyze(self, plan: SQLPlan, rows: list[dict[str, Any]]) -> str:
        if not rows:
            return "No rows were returned. Narrow or adjust the analysis question."

        first = rows[0]
        question = plan.question

        if plan.analysis_type == "sales_trend":
            return self._sales_trend(rows)
        if plan.analysis_type == "regional_growth":
            return (
                f"Fastest growing region: {first.get('region')}. "
                f"2025 revenue: {_money(first.get('revenue_2025'))}. "
                f"Growth rate: {_pct(first.get('growth_rate'))}."
            )
        if plan.analysis_type == "channel_conversion":
            return (
                f"Lowest conversion channel: {first.get('channel')}. "
                f"Leads: {first.get('leads')}. Conversions: {first.get('conversions')}. "
                f"Conversion rate: {_pct(first.get('conversion_rate'))}."
            )
        if "category" in first and "ticket_count" in first:
            return (
                f"Top support ticket category: {first.get('category')} "
                f"with {first.get('ticket_count')} tickets."
            )
        if "avg_resolution_hours" in first:
            return f"Average P1 resolution time is {first.get('avg_resolution_hours')} hours."
        if "avg_satisfaction_score" in first:
            return (
                f"Lowest satisfaction category: {first.get('category')}. "
                f"Average score: {first.get('avg_satisfaction_score')}."
            )
        if "product_line" in first and "total_revenue" in first and "华东" in question:
            return f"Top product line in East China: {first.get('product_line')} with revenue {_money(first.get('total_revenue'))}."
        if "industry" in first:
            return f"Top industry by revenue: {first.get('industry')} with revenue {_money(first.get('total_revenue'))}."
        if "roi" in first:
            return f"Highest ROI channel: {first.get('channel')} with ROI {_pct(first.get('roi'))}."
        if "new_customers" in first:
            return f"Region with the most new customers: {first.get('region')} ({first.get('new_customers')})."
        if "gross_margin" in first and "product_line" in first:
            return f"Highest gross-margin product line: {first.get('product_line')} at {_pct(first.get('gross_margin'))}."
        return f"Query completed with {len(rows)} rows."

    @staticmethod
    def _sales_trend(rows: list[dict[str, Any]]) -> str:
        first = rows[0]
        last = rows[-1]
        first_revenue = float(first.get("total_revenue") or 0)
        last_revenue = float(last.get("total_revenue") or 0)
        peak = max(rows, key=lambda row: float(row.get("total_revenue") or 0))
        period_key = "quarter" if "quarter" in first else "month" if "month" in first else None
        if period_key is None:
            return f"Revenue trend query completed with {len(rows)} periods."
        direction = "upward" if last_revenue >= first_revenue else "downward"
        return (
            f"Revenue shows an {direction} trend. "
            f"From {first.get(period_key)} {_money(first_revenue)} to {last.get(period_key)} {_money(last_revenue)}. "
            f"Peak period: {peak.get(period_key)} with {_money(peak.get('total_revenue'))}."
        )
