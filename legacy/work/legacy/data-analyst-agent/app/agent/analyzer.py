from __future__ import annotations

from typing import Any

from app.schemas.data_agent import SQLPlan


def _pct(value: Any) -> str:
    try:
        return f"{float(value) * 100:.1f}%"
    except (TypeError, ValueError):
        return "无法计算"


def _money(value: Any) -> str:
    try:
        return f"{float(value):,.0f}"
    except (TypeError, ValueError):
        return str(value)


class ResultAnalyzer:
    def analyze(self, plan: SQLPlan, rows: list[dict[str, Any]]) -> str:
        if not rows:
            return "本次查询没有返回数据，建议检查时间范围或筛选条件。"

        question = plan.question
        first = rows[0]

        if plan.analysis_type == "sales_trend":
            return self._sales_trend(rows)
        if plan.analysis_type == "regional_growth":
            return (
                f"增长最快的区域是{first.get('region')}，2025 年收入为 {_money(first.get('revenue_2025'))}，"
                f"相对 2024 年增长 {_pct(first.get('growth_rate'))}。"
            )
        if plan.analysis_type == "channel_conversion":
            return (
                f"转化率最低的渠道是{first.get('channel')}，线索数 {first.get('leads')}，"
                f"转化数 {first.get('conversions')}，转化率 {_pct(first.get('conversion_rate'))}。"
            )
        if "P1" in question.upper() and "avg_resolution_hours" in first:
            return f"P1 工单平均解决时间是 {first.get('avg_resolution_hours')} 小时，样本量 {first.get('ticket_count')} 个。"
        if "满意度" in question and "avg_satisfaction_score" in first:
            return (
                f"满意度最低的问题类别是{first.get('category')}，平均满意度 "
                f"{first.get('avg_satisfaction_score')}，样本量 {first.get('ticket_count')} 个。"
            )
        if "华东" in question and "product_line" in first:
            return f"华东地区收入最高的产品线是{first.get('product_line')}，收入 {_money(first.get('total_revenue'))}。"
        if "行业" in question and "industry" in first:
            return (
                f"贡献收入最高的客户行业是{first.get('industry')}，收入 {_money(first.get('total_revenue'))}，"
                f"涉及客户 {first.get('customer_count')} 个。"
            )
        if "ROI" in question.upper() and "roi" in first:
            return (
                f"市场投放 ROI 最高的渠道是{first.get('channel')}，ROI 为 {_pct(first.get('roi'))}。"
                "该口径按每个转化 800 元估算收入。"
            )
        if "新增客户" in question and "new_customers" in first:
            return f"最新月份新增客户最多来自{first.get('region')}，新增 {first.get('new_customers')} 个。"
        if "gross_margin" in first and "product_line" in first:
            return (
                f"毛利率排名第一的产品线是{first.get('product_line')}，毛利率 {_pct(first.get('gross_margin'))}，"
                f"收入 {_money(first.get('total_revenue'))}。"
            )
        return f"已完成查询，共返回 {len(rows)} 行结果。"

    @staticmethod
    def _sales_trend(rows: list[dict[str, Any]]) -> str:
        first = rows[0]
        last = rows[-1]
        try:
            first_revenue = float(first.get("total_revenue") or 0)
            last_revenue = float(last.get("total_revenue") or 0)
        except (TypeError, ValueError):
            first_revenue = last_revenue = 0
        peak = max(rows, key=lambda row: float(row.get("total_revenue") or 0))
        direction = "上升" if last_revenue >= first_revenue else "下降"
        return (
            f"2025 年季度营收整体呈{direction}趋势，"
            f"{first.get('quarter')} 为 {_money(first_revenue)}，{last.get('quarter')} 为 {_money(last_revenue)}；"
            f"峰值出现在 {peak.get('quarter')}，营收 {_money(peak.get('total_revenue'))}。"
        )

