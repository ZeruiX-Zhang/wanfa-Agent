from __future__ import annotations

from datetime import datetime, timezone
import time
from uuid import uuid4

from analyst_core.agent.analyzer import ResultAnalyzer
from analyst_core.agent.intent import detect_blocked_request
from analyst_core.chart.generator import ChartGenerator
from analyst_core.core.config import Settings, get_settings
from analyst_core.db.schema import retrieve_schema
from analyst_core.schemas.data_agent import (
    ChartResult,
    DataAgentQueryRequest,
    DataAgentQueryResponse,
    DataAgentTrace,
    SQLExecutionResult,
    SQLPlan,
    SQLValidationResult,
)
from analyst_core.sql.executor import ReadOnlySQLExecutor
from analyst_core.sql.generator import SQLPlanGenerator
from analyst_core.sql.safety import SQLSafetyChecker
from analyst_core.trace.store import TraceStore


class DataAnalystAgent:
    def __init__(self, settings: Settings | None = None, enable_trace: bool = True):
        self.settings = settings or get_settings()
        self.plan_generator = SQLPlanGenerator()
        self.safety_checker = SQLSafetyChecker(max_result_rows=self.settings.max_result_rows)
        self.executor = ReadOnlySQLExecutor(self.settings)
        self.analyzer = ResultAnalyzer()
        self.chart_generator = ChartGenerator(self.settings)
        self.trace_store = TraceStore(self.settings) if enable_trace else None

    def run(self, request: DataAgentQueryRequest) -> DataAgentQueryResponse:
        run_id = "run_" + uuid4().hex[:12]
        trace_id = "trace_" + uuid4().hex[:12]
        created_at = datetime.now(timezone.utc)
        started = time.perf_counter()
        sql_plan: SQLPlan | None = None
        execution: SQLExecutionResult | None = None
        chart_result: ChartResult | None = None

        schema_info = retrieve_schema(self.settings)
        blocked, reason, blocked_keywords = detect_blocked_request(request.question)
        if blocked:
            validation = SQLValidationResult(
                is_valid=False,
                original_sql=request.question,
                sanitized_sql=None,
                reasons=[reason],
                blocked_keywords=blocked_keywords,
                enforced_limit=None,
                max_result_rows=self.settings.max_result_rows,
            )
            final_answer = "Request rejected before SQL generation due to safety rules."
            return self._finish(
                run_id=run_id,
                trace_id=trace_id,
                status="rejected",
                request=request,
                schema_used=[],
                sql_plan=None,
                validation=validation,
                execution=None,
                chart_result=None,
                final_answer=final_answer,
                created_at=created_at,
                started=started,
            )

        sql_plan = self.plan_generator.generate(request.question, schema_info)
        validation = self.safety_checker.validate(sql_plan.sql)
        if not validation.is_valid or not validation.sanitized_sql:
            final_answer = "Request rejected because the generated SQL did not pass safety validation."
            return self._finish(
                run_id=run_id,
                trace_id=trace_id,
                status="rejected",
                request=request,
                schema_used=sql_plan.tables,
                sql_plan=sql_plan,
                validation=validation,
                execution=None,
                chart_result=None,
                final_answer=final_answer,
                created_at=created_at,
                started=started,
            )

        execution = self.executor.execute(validation.sanitized_sql)
        if execution.error:
            final_answer = f"SQL execution failed: {execution.error}"
            return self._finish(
                run_id=run_id,
                trace_id=trace_id,
                status="failed",
                request=request,
                schema_used=sql_plan.tables,
                sql_plan=sql_plan,
                validation=validation,
                execution=execution,
                chart_result=None,
                final_answer=final_answer,
                created_at=created_at,
                started=started,
            )

        final_answer = self.analyzer.analyze(sql_plan, execution.rows)
        chart_result = self.chart_generator.generate(run_id, sql_plan, execution)
        return self._finish(
            run_id=run_id,
            trace_id=trace_id,
            status="completed",
            request=request,
            schema_used=sql_plan.tables,
            sql_plan=sql_plan,
            validation=validation,
            execution=execution,
            chart_result=chart_result,
            final_answer=final_answer,
            created_at=created_at,
            started=started,
        )

    def _finish(
        self,
        *,
        run_id: str,
        trace_id: str,
        status: str,
        request: DataAgentQueryRequest,
        schema_used: list[str],
        sql_plan: SQLPlan | None,
        validation: SQLValidationResult,
        execution: SQLExecutionResult | None,
        chart_result: ChartResult | None,
        final_answer: str,
        created_at: datetime,
        started: float,
    ) -> DataAgentQueryResponse:
        finished_at = datetime.now(timezone.utc)
        latency_ms = int((time.perf_counter() - started) * 1000)
        executed_sql = execution.executed_sql if execution else None
        row_count = execution.row_count if execution else 0
        trace = DataAgentTrace(
            run_id=run_id,
            trace_id=trace_id,
            question=request.question,
            schema_used=schema_used,
            sql_plan=sql_plan,
            sql_validation=validation,
            executed_sql=executed_sql,
            row_count=row_count,
            chart_result=chart_result,
            final_answer=final_answer,
            latency_ms=latency_ms,
            created_at=created_at,
            finished_at=finished_at,
        )
        if self.trace_store is not None:
            self.trace_store.append(trace)

        return DataAgentQueryResponse(
            run_id=run_id,
            trace_id=trace_id,
            status=status,
            question=request.question,
            final_answer=final_answer,
            sql_plan=sql_plan,
            sql=validation.sanitized_sql,
            table_columns=execution.columns if execution else [],
            table_rows=execution.rows if execution else [],
            row_count=row_count,
            query_latency_ms=latency_ms,
            sql_validation=validation,
            execution=execution,
            chart=chart_result,
            chart_url=chart_result.chart_url if chart_result else None,
            trace_url=f"/api/v1/runs/{run_id}" if request.include_trace else None,
            created_at=created_at,
            finished_at=finished_at,
        )
