"""Pydantic models for LLM responses and internal data structures."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class ColumnMeta(BaseModel):
    column_name: str
    data_type: str
    is_nullable: bool = True
    is_primary_key: bool = False
    sample_values: list[Any] = Field(default_factory=list)
    distinct_values: Optional[list[Any]] = Field(
        default=None,
        description="All distinct values for low-cardinality categorical columns",
    )


class ForeignKeyMeta(BaseModel):
    column_name: str
    foreign_table_schema: str
    foreign_table_name: str
    foreign_column_name: str


class TableMeta(BaseModel):
    schema_name: str
    table_name: str
    columns: list[ColumnMeta] = Field(default_factory=list)
    foreign_keys: list[ForeignKeyMeta] = Field(default_factory=list)
    row_count_estimate: Optional[int] = None


class AnalysisPlan(BaseModel):
    """Strict schema the LLM must return."""

    analysis_summary: str
    sql: str
    python_analysis_code: str
    needs_visualization: bool = False
    visualization_type: Optional[str] = None
    visualization_title: Optional[str] = None
    visualization_code: Optional[str] = None
    result_interpretation: str = ""
    assumptions: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class SQLValidationResult(BaseModel):
    is_valid: bool
    normalized_sql: str = ""
    error: Optional[str] = None


class QueryResult(BaseModel):
    model_config = {"arbitrary_types_allowed": True}

    success: bool
    row_count: int = 0
    truncated: bool = False
    execution_time_ms: float = 0.0
    error: Optional[str] = None
    columns: list[str] = Field(default_factory=list)


class RunMetadata(BaseModel):
    run_id: str = Field(default_factory=lambda: uuid4().hex[:12])
    timestamp_utc: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    question: str = ""
    selected_tables: list[str] = Field(default_factory=list)
    execution_time_ms: float = 0.0
    row_count: int = 0
    success: bool = False
    warnings: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    error: Optional[str] = None
