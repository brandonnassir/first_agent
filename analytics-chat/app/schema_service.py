"""Builds rich schema context for the LLM from selected tables."""

from __future__ import annotations

import logging
from typing import Any, Optional

from app.config import AppConfig
from app.db import Database
from app.models import ColumnMeta, ForeignKeyMeta, TableMeta

logger = logging.getLogger(__name__)


class SchemaService:
    def __init__(self, db: Database, config: AppConfig) -> None:
        self._db = db
        self._config = config

    def get_table_meta(self, schema: str, table: str) -> TableMeta:
        """Gather full metadata for a single table."""
        columns_raw = self._db.get_column_metadata(schema, table)
        pk_cols = set(self._db.get_primary_keys(schema, table))
        fk_raw = self._db.get_foreign_keys(schema, table)

        sample_rows = self._safe_sample(schema, table)

        _TEXT_TYPES = {"text", "character varying", "character", "varchar", "char"}

        columns: list[ColumnMeta] = []
        for col in columns_raw:
            col_name = col["column_name"]
            sample_vals = [
                row.get(col_name) for row in sample_rows if row.get(col_name) is not None
            ]

            distinct_vals = None
            if col["data_type"] in _TEXT_TYPES:
                distinct_vals = self._safe_distinct(schema, table, col_name)

            columns.append(
                ColumnMeta(
                    column_name=col_name,
                    data_type=col["data_type"],
                    is_nullable=col["is_nullable"],
                    is_primary_key=col_name in pk_cols,
                    sample_values=sample_vals[: self._config.sample_rows],
                    distinct_values=distinct_vals,
                )
            )

        foreign_keys = [ForeignKeyMeta(**fk) for fk in fk_raw]
        row_count = self._db.get_row_count_estimate(schema, table)

        return TableMeta(
            schema_name=schema,
            table_name=table,
            columns=columns,
            foreign_keys=foreign_keys,
            row_count_estimate=row_count,
        )

    def build_schema_context(
        self, selected_tables: list[tuple[str, str]]
    ) -> list[dict[str, Any]]:
        """Return JSON-serialisable schema context for a list of (schema, table) pairs."""
        context: list[dict[str, Any]] = []
        for schema, table in selected_tables:
            try:
                meta = self.get_table_meta(schema, table)
                context.append(meta.model_dump(mode="json"))
            except Exception:
                logger.exception("Failed to gather metadata for %s.%s", schema, table)
                context.append(
                    {
                        "schema_name": schema,
                        "table_name": table,
                        "error": "Could not retrieve metadata",
                    }
                )
        return context

    def _safe_sample(self, schema: str, table: str) -> list[dict]:
        try:
            return self._db.fetch_sample_rows(schema, table, limit=self._config.sample_rows)
        except Exception:
            logger.warning("Could not fetch sample rows for %s.%s", schema, table)
            return []

    def _safe_distinct(self, schema: str, table: str, column: str) -> Optional[list]:
        try:
            return self._db.get_distinct_values(schema, table, column)
        except Exception:
            logger.warning(
                "Could not fetch distinct values for %s.%s.%s", schema, table, column
            )
            return None
