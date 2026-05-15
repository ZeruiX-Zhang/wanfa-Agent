from __future__ import annotations

from dataclasses import dataclass

from analyst_core.agent.pipeline import DataAnalystAgent
from analyst_core.core.config import Settings, get_settings
from analyst_core.schemas.data_agent import DataAgentQueryRequest, DataAgentQueryResponse
from platform_common.models import DataArtifact


@dataclass
class AnalysisServiceResult:
    run_id: str
    trace_id: str
    status: str
    final_answer: str
    sql: str | None
    row_count: int
    response: DataAgentQueryResponse
    data_artifacts: list[DataArtifact]


def _build_artifacts(response: DataAgentQueryResponse) -> list[DataArtifact]:
    artifacts = [
        DataArtifact(
            kind="table",
            name="query-result",
            preview=f"{response.row_count} rows",
            metadata={"columns": response.table_columns, "rows": response.table_rows[:5]},
        )
    ]
    if response.sql:
        artifacts.append(
            DataArtifact(
                kind="sql",
                name="validated-sql",
                preview=response.sql,
                metadata={"analysis_type": response.sql_plan.analysis_type if response.sql_plan else None},
            )
        )
    if response.chart and response.chart.generated:
        artifacts.append(
            DataArtifact(
                kind="chart",
                name=response.chart.chart_type,
                url=response.chart.chart_url,
                path=response.chart.chart_path,
                preview=response.chart.chart_url,
            )
        )
    return artifacts


def run_analysis(
    question: str,
    include_trace: bool = False,
    enable_internal_trace: bool = False,
    settings: Settings | None = None,
) -> AnalysisServiceResult:
    actual_settings = settings or get_settings()
    agent = DataAnalystAgent(settings=actual_settings, enable_trace=enable_internal_trace)
    response = agent.run(DataAgentQueryRequest(question=question, include_trace=include_trace))
    return AnalysisServiceResult(
        run_id=response.run_id,
        trace_id=response.trace_id,
        status=response.status,
        final_answer=response.final_answer,
        sql=response.sql,
        row_count=response.row_count,
        response=response,
        data_artifacts=_build_artifacts(response),
    )
