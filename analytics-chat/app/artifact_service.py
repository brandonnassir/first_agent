"""Persist all generated artifacts for a single analytics run."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Optional

import pandas as pd
import plotly.graph_objects as go

from app.models import AnalysisPlan, RunMetadata
from app.utils import generate_run_id

logger = logging.getLogger(__name__)


class ArtifactService:
    def __init__(self, base_dir: Path) -> None:
        self._base_dir = base_dir

    def save_run(
        self,
        *,
        question: str,
        selected_tables: list[str],
        schema_context: list[dict[str, Any]],
        llm_request: dict[str, Any],
        llm_response: dict[str, Any],
        plan: AnalysisPlan,
        df: Optional[pd.DataFrame],
        fig: Optional[go.Figure],
        metadata: RunMetadata,
    ) -> Path:
        """Write every artifact to a new run directory and return its path."""
        run_id = generate_run_id()
        run_dir = self._base_dir / run_id
        run_dir.mkdir(parents=True, exist_ok=True)

        self._write_text(run_dir / "prompt.txt", question)
        self._write_json(run_dir / "selected_tables.json", selected_tables)
        self._write_json(run_dir / "schema_context.json", schema_context)
        self._write_json(run_dir / "llm_request.json", llm_request)
        self._write_json(run_dir / "llm_response.json", llm_response)
        self._write_text(run_dir / "generated_sql.sql", plan.sql)
        self._write_text(run_dir / "analysis.py", plan.python_analysis_code)

        if plan.visualization_code:
            self._write_text(run_dir / "chart.py", plan.visualization_code)

        if df is not None:
            try:
                df.to_csv(run_dir / "result.csv", index=False)
            except Exception:
                logger.warning("Could not save result.csv")
            try:
                df.to_parquet(run_dir / "result.parquet", index=False)
            except Exception:
                logger.warning("Could not save result.parquet")

        if fig is not None:
            try:
                fig.write_html(str(run_dir / "chart.html"))
            except Exception:
                logger.warning("Could not save chart.html")
            try:
                fig.write_image(str(run_dir / "chart.png"), width=1200, height=700)
            except Exception:
                logger.warning("Could not save chart.png (kaleido may not be installed)")

        summary_md = self._build_summary(plan, metadata)
        self._write_text(run_dir / "summary.md", summary_md)

        metadata.run_id = run_id
        self._write_json(run_dir / "metadata.json", metadata.model_dump(mode="json"))

        logger.info("Artifacts saved → %s", run_dir)
        return run_dir

    @staticmethod
    def _write_text(path: Path, content: str) -> None:
        path.write_text(content, encoding="utf-8")

    @staticmethod
    def _write_json(path: Path, data: Any) -> None:
        path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")

    @staticmethod
    def _build_summary(plan: AnalysisPlan, meta: RunMetadata) -> str:
        lines = [
            f"# Analytics Run Summary",
            "",
            f"**Question:** {meta.question}",
            f"**Tables:** {', '.join(meta.selected_tables)}",
            f"**Timestamp:** {meta.timestamp_utc}",
            f"**Rows returned:** {meta.row_count}",
            f"**Execution time:** {meta.execution_time_ms:.1f} ms",
            "",
            "## Analysis Summary",
            plan.analysis_summary,
            "",
            "## Result Interpretation",
            plan.result_interpretation,
            "",
        ]
        if plan.assumptions:
            lines.append("## Assumptions")
            for a in plan.assumptions:
                lines.append(f"- {a}")
            lines.append("")
        if plan.warnings or meta.warnings:
            lines.append("## Warnings")
            for w in list(plan.warnings) + list(meta.warnings):
                lines.append(f"- {w}")
            lines.append("")
        return "\n".join(lines)
