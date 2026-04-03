"""Execute validated SQL and return results as a pandas DataFrame."""

from __future__ import annotations

import logging
import time
from typing import Optional

import pandas as pd
from sqlalchemy import text

from app.config import AppConfig
from app.db import Database
from app.models import QueryResult
from app.sql_validator import maybe_add_limit, validate_sql

logger = logging.getLogger(__name__)


class QueryService:
    def __init__(self, db: Database, config: AppConfig) -> None:
        self._db = db
        self._config = config

    def execute(self, sql: str) -> tuple[Optional[pd.DataFrame], QueryResult]:
        """Validate, optionally add LIMIT, execute, and return (df, metadata)."""
        validation = validate_sql(sql)
        if not validation.is_valid:
            return None, QueryResult(
                success=False, error=f"SQL validation failed: {validation.error}"
            )

        safe_sql = maybe_add_limit(validation.normalized_sql, self._config.max_result_rows)

        start = time.perf_counter()
        try:
            with self._db.engine.connect() as conn:
                result = conn.execute(text(safe_sql))
                columns = list(result.keys())
                rows = result.fetchall()
        except Exception as exc:
            elapsed = (time.perf_counter() - start) * 1000
            logger.exception("SQL execution error")
            return None, QueryResult(
                success=False,
                execution_time_ms=elapsed,
                error=str(exc),
            )

        elapsed = (time.perf_counter() - start) * 1000
        df = pd.DataFrame(rows, columns=columns)

        truncated = len(df) > self._config.display_rows
        display_df = df.head(self._config.display_rows) if truncated else df

        return display_df, QueryResult(
            success=True,
            row_count=len(df),
            truncated=truncated,
            execution_time_ms=elapsed,
            columns=columns,
        )

    def execute_full(self, sql: str) -> tuple[Optional[pd.DataFrame], QueryResult]:
        """Same as execute but returns the full un-truncated DataFrame for artifacts."""
        validation = validate_sql(sql)
        if not validation.is_valid:
            return None, QueryResult(
                success=False, error=f"SQL validation failed: {validation.error}"
            )

        safe_sql = maybe_add_limit(validation.normalized_sql, self._config.max_result_rows)

        start = time.perf_counter()
        try:
            with self._db.engine.connect() as conn:
                result = conn.execute(text(safe_sql))
                columns = list(result.keys())
                rows = result.fetchall()
        except Exception as exc:
            elapsed = (time.perf_counter() - start) * 1000
            logger.exception("SQL execution error")
            return None, QueryResult(
                success=False,
                execution_time_ms=elapsed,
                error=str(exc),
            )

        elapsed = (time.perf_counter() - start) * 1000
        df = pd.DataFrame(rows, columns=columns)

        return df, QueryResult(
            success=True,
            row_count=len(df),
            truncated=False,
            execution_time_ms=elapsed,
            columns=columns,
        )
