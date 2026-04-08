"""PostgreSQL connection management via SQLAlchemy."""

from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Generator, Optional

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import AppConfig

logger = logging.getLogger(__name__)


class Database:
    """Thin wrapper around a SQLAlchemy engine for read-only analytics."""

    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._engine: Engine = create_engine(
            config.db.url,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=2,
            connect_args={"options": f"-c statement_timeout={config.query_timeout_seconds * 1000}"},
        )
        self._session_factory = sessionmaker(bind=self._engine)

    @property
    def engine(self) -> Engine:
        return self._engine

    def test_connection(self) -> bool:
        """Return True if the database is reachable."""
        try:
            with self._engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True
        except Exception:
            logger.exception("Database connectivity test failed")
            return False

    @contextmanager
    def session(self) -> Generator[Session, None, None]:
        sess = self._session_factory()
        try:
            yield sess
        finally:
            sess.close()

    def list_schemas(self) -> list[str]:
        """Return non-system schema names."""
        query = text(
            "SELECT schema_name FROM information_schema.schemata "
            "WHERE schema_name NOT IN ('pg_catalog', 'information_schema', 'pg_toast') "
            "ORDER BY schema_name"
        )
        with self._engine.connect() as conn:
            return [row[0] for row in conn.execute(query)]

    def list_tables(self, schema: str = "public") -> list[str]:
        """Return table names within *schema*."""
        query = text(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = :schema AND table_type = 'BASE TABLE' "
            "ORDER BY table_name"
        )
        with self._engine.connect() as conn:
            return [row[0] for row in conn.execute(query, {"schema": schema})]

    def get_column_metadata(self, schema: str, table: str) -> list[dict]:
        """Return column-level metadata from information_schema."""
        query = text(
            "SELECT column_name, data_type, is_nullable, column_default "
            "FROM information_schema.columns "
            "WHERE table_schema = :schema AND table_name = :table "
            "ORDER BY ordinal_position"
        )
        with self._engine.connect() as conn:
            rows = conn.execute(query, {"schema": schema, "table": table}).fetchall()
        return [
            {
                "column_name": r[0],
                "data_type": r[1],
                "is_nullable": r[2] == "YES",
                "column_default": r[3],
            }
            for r in rows
        ]

    def get_primary_keys(self, schema: str, table: str) -> list[str]:
        query = text(
            "SELECT kcu.column_name "
            "FROM information_schema.table_constraints tc "
            "JOIN information_schema.key_column_usage kcu "
            "  ON tc.constraint_name = kcu.constraint_name "
            "  AND tc.table_schema = kcu.table_schema "
            "WHERE tc.constraint_type = 'PRIMARY KEY' "
            "  AND tc.table_schema = :schema "
            "  AND tc.table_name = :table "
            "ORDER BY kcu.ordinal_position"
        )
        with self._engine.connect() as conn:
            return [row[0] for row in conn.execute(query, {"schema": schema, "table": table})]

    def get_foreign_keys(self, schema: str, table: str) -> list[dict]:
        query = text(
            "SELECT kcu.column_name, "
            "       ccu.table_schema AS foreign_table_schema, "
            "       ccu.table_name AS foreign_table_name, "
            "       ccu.column_name AS foreign_column_name "
            "FROM information_schema.table_constraints tc "
            "JOIN information_schema.key_column_usage kcu "
            "  ON tc.constraint_name = kcu.constraint_name "
            "  AND tc.table_schema = kcu.table_schema "
            "JOIN information_schema.constraint_column_usage ccu "
            "  ON tc.constraint_name = ccu.constraint_name "
            "WHERE tc.constraint_type = 'FOREIGN KEY' "
            "  AND tc.table_schema = :schema "
            "  AND tc.table_name = :table"
        )
        with self._engine.connect() as conn:
            rows = conn.execute(query, {"schema": schema, "table": table}).fetchall()
        return [
            {
                "column_name": r[0],
                "foreign_table_schema": r[1],
                "foreign_table_name": r[2],
                "foreign_column_name": r[3],
            }
            for r in rows
        ]

    def get_row_count_estimate(self, schema: str, table: str) -> int | None:
        """Fast approximate row count from pg_class."""
        query = text(
            "SELECT reltuples::bigint FROM pg_class c "
            "JOIN pg_namespace n ON n.oid = c.relnamespace "
            "WHERE n.nspname = :schema AND c.relname = :table"
        )
        with self._engine.connect() as conn:
            result = conn.execute(query, {"schema": schema, "table": table}).fetchone()
        if result and result[0] >= 0:
            return int(result[0])
        return None

    def get_distinct_values(
        self, schema: str, table: str, column: str, max_distinct: int = 50
    ) -> Optional[list]:
        """Return distinct values for a column if cardinality <= *max_distinct*, else None."""
        safe_id = f'"{schema}"."{table}"'
        count_q = text(
            f'SELECT COUNT(DISTINCT "{column}") FROM {safe_id}'
        )
        with self._engine.connect() as conn:
            count = conn.execute(count_q).scalar() or 0
            if count > max_distinct:
                return None
            vals_q = text(
                f'SELECT DISTINCT "{column}" FROM {safe_id} '
                f'WHERE "{column}" IS NOT NULL ORDER BY 1'
            )
            return [row[0] for row in conn.execute(vals_q)]

    def fetch_sample_rows(self, schema: str, table: str, limit: int = 5) -> list[dict]:
        """Return a small sample of rows for schema context."""
        safe_id = f'"{schema}"."{table}"'
        query = text(f"SELECT * FROM {safe_id} LIMIT :lim")
        with self._engine.connect() as conn:
            result = conn.execute(query, {"lim": limit})
            columns = list(result.keys())
            rows = result.fetchall()
        return [dict(zip(columns, row)) for row in rows]
