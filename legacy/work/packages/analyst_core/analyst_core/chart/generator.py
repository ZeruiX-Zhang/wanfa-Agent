from __future__ import annotations

import math
import struct
import zlib
from pathlib import Path
from typing import Any

from analyst_core.core.config import PROJECT_ROOT, Settings, get_settings
from analyst_core.schemas.data_agent import ChartResult, ChartSpec, SQLExecutionResult, SQLPlan


class ChartGenerator:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()

    def generate(self, run_id: str, plan: SQLPlan, execution: SQLExecutionResult) -> ChartResult:
        spec = self._infer_spec(plan, execution)
        if spec.chart_type == "none":
            return ChartResult(chart_type="none", generated=False)
        if not spec.x_column or not spec.y_column:
            return ChartResult(chart_type=spec.chart_type, generated=False, chart_error="Missing chart columns.")
        if not execution.rows:
            return ChartResult(chart_type=spec.chart_type, generated=False, chart_error="No rows to plot.")

        output_dir = self.settings.chart_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{run_id}.png"

        try:
            self._draw_with_matplotlib(output_path, execution.rows, spec)
        except Exception:
            try:
                self._draw_fallback_png(output_path, execution.rows, spec)
            except Exception as exc:
                return ChartResult(chart_type=spec.chart_type, generated=False, chart_error=f"Chart generation failed: {exc}")

        return ChartResult(
            chart_type=spec.chart_type,
            chart_path=self._display_path(output_path),
            chart_url=f"/artifacts/charts/{output_path.name}",
            generated=True,
        )

    def _infer_spec(self, plan: SQLPlan, execution: SQLExecutionResult) -> ChartSpec:
        columns = execution.columns
        if plan.chart_type == "none":
            return ChartSpec(chart_type="none", title="No chart")
        if "quarter" in columns and "total_revenue" in columns:
            return ChartSpec(chart_type="line", x_column="quarter", y_column="total_revenue", title="Quarterly Revenue")
        if "month" in columns and "total_revenue" in columns:
            return ChartSpec(chart_type="line", x_column="month", y_column="total_revenue", title="Monthly Revenue")
        if "category" in columns and "ticket_count" in columns:
            return ChartSpec(chart_type=plan.chart_type, x_column="category", y_column="ticket_count", title="Support Ticket Distribution")
        if "growth_rate" in columns:
            return ChartSpec(chart_type="bar", x_column="region", y_column="growth_rate", title="Regional Growth")
        if "conversion_rate" in columns:
            return ChartSpec(chart_type="bar", x_column="channel", y_column="conversion_rate", title="Channel Conversion")
        if "roi" in columns:
            return ChartSpec(chart_type="bar", x_column="channel", y_column="roi", title="Channel ROI")
        if "gross_margin" in columns:
            return ChartSpec(chart_type="bar", x_column="product_line", y_column="gross_margin", title="Gross Margin")
        if "avg_satisfaction_score" in columns:
            return ChartSpec(chart_type="bar", x_column="category", y_column="avg_satisfaction_score", title="Satisfaction")
        if "total_revenue" in columns:
            x_col = "product_line" if "product_line" in columns else "industry" if "industry" in columns else columns[0]
            return ChartSpec(chart_type="bar", x_column=x_col, y_column="total_revenue", title="Revenue Comparison")
        if "new_customers" in columns:
            return ChartSpec(chart_type="bar", x_column="region", y_column="new_customers", title="New Customers")
        numeric_col = self._first_numeric_column(execution.rows, columns)
        return ChartSpec(chart_type=plan.chart_type, x_column=columns[0] if columns else None, y_column=numeric_col, title=plan.question[:40])

    @staticmethod
    def _first_numeric_column(rows: list[dict[str, Any]], columns: list[str]) -> str | None:
        for column in columns:
            values = [row.get(column) for row in rows[:5]]
            if values and all(isinstance(value, (int, float)) or value is None for value in values):
                return column
        return None

    @staticmethod
    def _draw_with_matplotlib(output_path: Path, rows: list[dict[str, Any]], spec: ChartSpec) -> None:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        labels = [str(row.get(spec.x_column, "")) for row in rows]
        values = [float(row.get(spec.y_column) or 0) for row in rows]
        fig, ax = plt.subplots(figsize=(9, 4.8), dpi=140)
        if spec.chart_type == "line":
            ax.plot(labels, values, marker="o", linewidth=2.2, color="#2563eb")
        elif spec.chart_type == "pie":
            ax.pie(values, labels=labels, autopct="%1.1f%%")
        else:
            ax.bar(labels, values, color="#16726d")
        ax.set_title(spec.title)
        if spec.chart_type != "pie":
            ax.set_xlabel(spec.x_column or "")
            ax.set_ylabel(spec.y_column or "")
            plt.xticks(rotation=20, ha="right")
        fig.tight_layout()
        fig.savefig(output_path)
        plt.close(fig)

    @staticmethod
    def _draw_fallback_png(output_path: Path, rows: list[dict[str, Any]], spec: ChartSpec) -> None:
        width, height = 640, 360
        margin_left, margin_bottom, margin_top, margin_right = 56, 48, 32, 24
        chart_width = width - margin_left - margin_right
        chart_height = height - margin_top - margin_bottom
        values = [float(row.get(spec.y_column) or 0) for row in rows[:12]]
        max_value = max(values) if values else 1.0
        min_value = min(values) if values else 0.0
        if math.isclose(max_value, min_value):
            max_value = min_value + 1.0

        pixels = bytearray([255, 255, 255] * width * height)

        def set_pixel(x: int, y: int, color: tuple[int, int, int]) -> None:
            if 0 <= x < width and 0 <= y < height:
                idx = (y * width + x) * 3
                pixels[idx:idx + 3] = bytes(color)

        def draw_line(x1: int, y1: int, x2: int, y2: int, color: tuple[int, int, int]) -> None:
            dx = abs(x2 - x1)
            dy = -abs(y2 - y1)
            sx = 1 if x1 < x2 else -1
            sy = 1 if y1 < y2 else -1
            err = dx + dy
            x, y = x1, y1
            while True:
                set_pixel(x, y, color)
                if x == x2 and y == y2:
                    break
                e2 = 2 * err
                if e2 >= dy:
                    err += dy
                    x += sx
                if e2 <= dx:
                    err += dx
                    y += sy

        axis_color = (80, 80, 80)
        draw_line(margin_left, margin_top, margin_left, height - margin_bottom, axis_color)
        draw_line(margin_left, height - margin_bottom, width - margin_right, height - margin_bottom, axis_color)

        if spec.chart_type == "line" and len(values) > 1:
            points: list[tuple[int, int]] = []
            for index, value in enumerate(values):
                x = margin_left + int(index * chart_width / max(len(values) - 1, 1))
                ratio = (value - min_value) / (max_value - min_value)
                y = height - margin_bottom - int(ratio * chart_height)
                points.append((x, y))
            for start, end in zip(points, points[1:]):
                draw_line(start[0], start[1], end[0], end[1], (37, 99, 235))
        else:
            bar_count = max(len(values), 1)
            slot = chart_width / bar_count
            bar_width = max(int(slot * 0.62), 8)
            for index, value in enumerate(values):
                ratio = (value - min_value) / (max_value - min_value)
                bar_height = int(ratio * chart_height)
                x0 = margin_left + int(index * slot + (slot - bar_width) / 2)
                x1 = min(x0 + bar_width, width - margin_right)
                y0 = height - margin_bottom - bar_height
                for y in range(y0, height - margin_bottom):
                    for x in range(x0, x1):
                        set_pixel(x, y, (22, 114, 109))

        raw = bytearray()
        for y in range(height):
            raw.append(0)
            raw.extend(pixels[y * width * 3:(y + 1) * width * 3])

        def chunk(chunk_type: bytes, data: bytes) -> bytes:
            return (
                struct.pack(">I", len(data))
                + chunk_type
                + data
                + struct.pack(">I", zlib.crc32(chunk_type + data) & 0xFFFFFFFF)
            )

        png = (
            b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(bytes(raw), level=6))
            + chunk(b"IEND", b"")
        )
        output_path.write_bytes(png)

    @staticmethod
    def _display_path(path: Path) -> str:
        try:
            return path.relative_to(PROJECT_ROOT).as_posix()
        except ValueError:
            return path.as_posix()
