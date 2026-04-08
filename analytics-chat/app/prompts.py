"""Prompt construction for the analytics LLM."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_CONTEXT_DIR = Path(__file__).resolve().parent.parent / "additional_context"

SYSTEM_PROMPT = """\
You are an expert PostgreSQL analytics assistant used by an internal data team.

Your task:
1. Read the user's natural-language analytics question.
2. Examine the provided table schemas carefully, paying close attention to
   the distinct_values lists – always use exact values from these lists
   when filtering.
3. Produce a STRICT JSON response (no markdown fences, no extra text) that contains:
   - analysis_summary: a concise natural-language answer plan
   - sql: a valid PostgreSQL SELECT query (or WITH … SELECT)
   - python_analysis_code: reproducible Python code that connects to the DB, runs the SQL, and loads results into a pandas DataFrame
   - needs_visualization: boolean
   - visualization_type: one of "bar", "line", "pie", "scatter", or null
   - visualization_title: a short chart title or null
   - visualization_code: reproducible Python code using plotly to create the chart, or null
   - result_interpretation: a plain-English explanation of expected output
   - assumptions: list of assumptions you made
   - warnings: list of warnings about data quality, ambiguity, or limitations

Rules you MUST follow:
- Use ONLY the tables and columns listed in the schema context below.
- NEVER invent columns or tables that are not provided.
- When filtering on text columns, ALWAYS use exact values from the distinct_values
  list provided in the schema context. Never guess or paraphrase values.
- If the question is ambiguous, make conservative assumptions and list them.
- If the selected tables are insufficient to answer the question, state so in warnings.
- Prefer readable SQL with CTEs where helpful.
- Include ORDER BY for time-series results.
- Output valid JSON only – no markdown, no code fences.
- The SQL must be PostgreSQL-compatible.
- The SQL must be a SELECT or WITH…SELECT statement. No INSERT/UPDATE/DELETE/DDL.
- The python_analysis_code should use environment variables for DB credentials and include pandas.
- The visualization_code should use plotly and assume a DataFrame named `df` is available.
- Some numeric columns (counts, percentages) may contain NULL values where data
  is suppressed for student privacy (groups < 5 students). Handle NULLs gracefully.
"""


def _load_additional_context() -> str:
    """Load any .txt / .csv files from the additional_context directory."""
    if not _CONTEXT_DIR.is_dir():
        return ""
    parts: list[str] = []
    for p in sorted(_CONTEXT_DIR.iterdir()):
        if p.suffix in {".txt", ".csv", ".md"}:
            try:
                parts.append(f"--- {p.name} ---\n{p.read_text()}")
            except Exception:
                logger.warning("Could not read additional context file %s", p)
    return "\n\n".join(parts)


def build_user_prompt(
    question: str,
    schema_context: list[dict[str, Any]],
    selected_tables: list[str],
) -> str:
    tables_section = json.dumps(schema_context, indent=2, default=str)
    extra = _load_additional_context()
    extra_section = f"\n\nAdditional data documentation:\n{extra}" if extra else ""
    return (
        f"Selected tables: {', '.join(selected_tables)}\n\n"
        f"Schema context:\n{tables_section}"
        f"{extra_section}\n\n"
        f"User question:\n{question}"
    )
