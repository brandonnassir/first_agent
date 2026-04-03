"""Orchestrator – ties all services together for a single analytics run."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from app.artifact_service import ArtifactService
from app.chart_service import ChartService
from app.config import AppConfig
from app.db import Database
from app.llm_service import LLMService
from app.models import AnalysisPlan, RunMetadata
from app.query_service import QueryService
from app.response_formatter import AnalysisResponse, build_response
from app.schema_service import SchemaService

logger = logging.getLogger(__name__)


def run_analysis(
    question: str,
    selected_tables: list[tuple[str, str]],
    config: AppConfig | None = None,
) -> AnalysisResponse:
    """End-to-end analytics pipeline.

    Parameters
    ----------
    question:
        Natural-language analytics question.
    selected_tables:
        List of (schema, table) tuples the user selected.
    config:
        Optional override; defaults to fresh AppConfig.
    """
    if config is None:
        from app.config import get_config
        config = get_config()

    db = Database(config)
    schema_svc = SchemaService(db, config)
    llm_svc = LLMService(config)
    query_svc = QueryService(db, config)
    chart_svc = ChartService()
    artifact_svc = ArtifactService(config.artifacts_dir)

    table_labels = [f"{s}.{t}" for s, t in selected_tables]

    # 1. Build schema context
    schema_context = schema_svc.build_schema_context(selected_tables)

    # 2. Call LLM
    plan, llm_req, llm_resp = llm_svc.generate_analysis_plan(
        question, schema_context, table_labels
    )

    # 3. Execute SQL
    display_df, query_result = query_svc.execute(plan.sql)
    full_df = display_df  # for artifact persistence
    if query_result.success:
        full_df_res, _ = query_svc.execute_full(plan.sql)
        if full_df_res is not None:
            full_df = full_df_res

    # 4. Render chart (trusted code only)
    figure = None
    chart_warnings: list[str] = []
    if plan.needs_visualization and display_df is not None:
        figure, chart_warnings = chart_svc.render(
            display_df,
            plan.visualization_type,
            plan.visualization_title,
        )

    # 5. Build metadata
    meta = RunMetadata(
        question=question,
        selected_tables=table_labels,
        execution_time_ms=query_result.execution_time_ms,
        row_count=query_result.row_count,
        success=query_result.success,
        warnings=chart_warnings,
        assumptions=plan.assumptions,
        error=query_result.error,
    )

    # 6. Persist artifacts
    try:
        run_dir = artifact_svc.save_run(
            question=question,
            selected_tables=table_labels,
            schema_context=schema_context,
            llm_request=llm_req,
            llm_response=llm_resp,
            plan=plan,
            df=full_df,
            fig=figure,
            metadata=meta,
        )
        artifacts_path = str(run_dir)
    except Exception:
        logger.exception("Failed to save artifacts")
        artifacts_path = ""

    # 7. Assemble response
    return build_response(
        plan=plan,
        df=display_df,
        query_result=query_result,
        figure=figure,
        chart_warnings=chart_warnings,
        metadata=meta,
        artifacts_path=artifacts_path,
    )
