"""Trusted chart rendering – never executes LLM code directly."""

from __future__ import annotations

import logging
from typing import Optional

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

logger = logging.getLogger(__name__)

SUPPORTED_CHART_TYPES = {"bar", "line", "pie", "scatter"}


class ChartService:
    """Generate plotly figures from a DataFrame and LLM hints."""

    def render(
        self,
        df: pd.DataFrame,
        visualization_type: Optional[str],
        visualization_title: Optional[str] = None,
    ) -> tuple[Optional[go.Figure], list[str]]:
        """Return (figure_or_None, warnings)."""
        warnings: list[str] = []

        if df.empty:
            warnings.append("Cannot create chart: result DataFrame is empty.")
            return None, warnings

        if not visualization_type:
            warnings.append("No visualization type specified.")
            return None, warnings

        vtype = visualization_type.strip().lower()
        if vtype not in SUPPORTED_CHART_TYPES:
            warnings.append(
                f"Unsupported visualization type '{visualization_type}'. "
                f"Supported: {', '.join(sorted(SUPPORTED_CHART_TYPES))}."
            )
            return None, warnings

        title = visualization_title or "Chart"

        try:
            fig = self._build_figure(df, vtype, title)
            return fig, warnings
        except Exception as exc:
            logger.exception("Chart rendering failed")
            warnings.append(f"Chart rendering error: {exc}")
            return None, warnings

    def _build_figure(
        self, df: pd.DataFrame, vtype: str, title: str
    ) -> go.Figure:
        x_col, y_col, cat_col = self._infer_columns(df, vtype)

        if vtype == "bar":
            fig = px.bar(df, x=x_col, y=y_col, color=cat_col, title=title)
        elif vtype == "line":
            fig = px.line(df, x=x_col, y=y_col, color=cat_col, title=title)
        elif vtype == "scatter":
            fig = px.scatter(df, x=x_col, y=y_col, color=cat_col, title=title)
        elif vtype == "pie":
            fig = px.pie(df, names=x_col, values=y_col, title=title)
        else:
            raise ValueError(f"Unsupported chart type: {vtype}")

        fig.update_layout(template="plotly_white")
        return fig

    @staticmethod
    def _infer_columns(
        df: pd.DataFrame, vtype: str
    ) -> tuple[str, Optional[str], Optional[str]]:
        """Heuristically pick x, y, and optional category columns."""
        cols = list(df.columns)

        numeric_cols = df.select_dtypes(include="number").columns.tolist()
        non_numeric_cols = [c for c in cols if c not in numeric_cols]
        datetime_cols = df.select_dtypes(include=["datetime", "datetimetz"]).columns.tolist()

        if vtype == "pie":
            names_col = non_numeric_cols[0] if non_numeric_cols else cols[0]
            values_col = numeric_cols[0] if numeric_cols else (cols[1] if len(cols) > 1 else cols[0])
            return names_col, values_col, None

        # For bar / line / scatter, prefer datetime or first non-numeric as x
        if datetime_cols:
            x = datetime_cols[0]
        elif non_numeric_cols:
            x = non_numeric_cols[0]
        else:
            x = cols[0]

        y = numeric_cols[0] if numeric_cols else (cols[1] if len(cols) > 1 else cols[0])

        cat: Optional[str] = None
        if len(non_numeric_cols) > 1:
            candidates = [c for c in non_numeric_cols if c != x]
            if candidates:
                cat = candidates[0]

        return x, y, cat
