from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path
from statistics import mean

from workflow_core.core.config import settings
from workflow_core.schemas.agent import CSVAnalysisResult
from workflow_core.security.policies import ensure_inside_finance_dir


NUMERIC_COLUMNS = ("revenue", "gross_margin", "customer_count")


def _safe_float(value: str) -> float:
    return float(value.strip())


def _mean(values: list[float]) -> float:
    return round(mean(values), 6) if values else 0.0


def _sum(values: list[float]) -> float:
    return round(sum(values), 6)


def _growth_rate(first: float, last: float) -> float:
    if first == 0:
        return 0.0
    return round((last - first) / first, 6)


def analyze_csv(path: str | Path | None = None) -> CSVAnalysisResult:
    csv_path = ensure_inside_finance_dir(Path(path) if path else settings.finance_csv)
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    with csv_path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        rows = list(reader)
        columns = reader.fieldnames or []

    quarter_values: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    region_values: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    metric_values: dict[str, list[float]] = defaultdict(list)
    region_revenue_by_quarter: dict[str, list[tuple[str, float]]] = defaultdict(list)

    for row in rows:
        quarter = row.get("quarter", "")
        region = row.get("region", "")
        for column in NUMERIC_COLUMNS:
            value = _safe_float(row.get(column, "0"))
            quarter_values[quarter][column].append(value)
            region_values[region][column].append(value)
            metric_values[column].append(value)
            if column == "revenue":
                region_revenue_by_quarter[region].append((quarter, value))

    quarter_summary = {
        quarter: {
            "revenue_sum": _sum(values["revenue"]),
            "gross_margin_mean": _mean(values["gross_margin"]),
            "customer_count_sum": _sum(values["customer_count"]),
        }
        for quarter, values in sorted(quarter_values.items())
    }
    region_summary = {
        region: {
            "revenue_sum": _sum(values["revenue"]),
            "gross_margin_mean": _mean(values["gross_margin"]),
            "customer_count_sum": _sum(values["customer_count"]),
        }
        for region, values in sorted(region_values.items())
    }
    metrics_summary = {
        column: {
            "mean": _mean(values),
            "max": round(max(values), 6) if values else 0.0,
            "min": round(min(values), 6) if values else 0.0,
        }
        for column, values in metric_values.items()
    }

    growth_rates: dict[str, float] = {}
    for region, values in region_revenue_by_quarter.items():
        ordered = sorted(values, key=lambda item: item[0])
        if ordered:
            growth_rates[region] = _growth_rate(ordered[0][1], ordered[-1][1])

    return CSVAnalysisResult(
        columns=columns,
        row_count=len(rows),
        quarter_summary=quarter_summary,
        region_summary=region_summary,
        metrics_summary=metrics_summary,
        growth_rates=growth_rates,
        fastest_growth_region=max(growth_rates, key=growth_rates.get) if growth_rates else None,
        calculation_logic="Aggregate by quarter and region, then compute revenue growth from first to last quarter.",
    )
