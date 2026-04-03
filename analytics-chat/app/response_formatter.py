"""Format the final response bundle for the Streamlit UI."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

import pandas as pd
import plotly.graph_objects as go

from app.models import AnalysisPlan, QueryResult, RunMetadata


@dataclass
class AnalysisResponse:
    """All artefacts the frontend needs to render a run."""

    success: bool = False
    error: Optional[str] = None

    # Natural-language
    analysis_summary: str = ""
    result_interpretation: str = ""
    assumptions: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    # Data
    df: Optional[pd.DataFrame] = None
    query_result: Optional[QueryResult] = None

    # Code artefacts
    sql: str = ""
    python_analysis_code: str = ""
    visualization_code: str = ""

    # Chart
    figure: Optional[go.Figure] = None

    # Metadata
    metadata: Optional[RunMetadata] = None
    artifacts_path: str = ""


def build_response(
    plan: AnalysisPlan,
    df: Optional[pd.DataFrame],
    query_result: QueryResult,
    figure: Optional[go.Figure],
    chart_warnings: list[str],
    metadata: RunMetadata,
    artifacts_path: str = "",
) -> AnalysisResponse:
    all_warnings = list(plan.warnings) + chart_warnings + list(metadata.warnings)
    return AnalysisResponse(
        success=query_result.success,
        error=query_result.error,
        analysis_summary=plan.analysis_summary,
        result_interpretation=plan.result_interpretation,
        assumptions=plan.assumptions,
        warnings=all_warnings,
        df=df,
        query_result=query_result,
        sql=plan.sql,
        python_analysis_code=plan.python_analysis_code,
        visualization_code=plan.visualization_code or "",
        figure=figure,
        metadata=metadata,
        artifacts_path=artifacts_path,
    )
