"""Tests for the query service module."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from app.config import AppConfig
from app.query_service import QueryService


@pytest.fixture()
def config():
    return AppConfig()


@pytest.fixture()
def mock_db():
    return MagicMock()


class TestQueryServiceExecute:
    def test_rejects_invalid_sql(self, mock_db, config):
        svc = QueryService(mock_db, config)
        df, result = svc.execute("DROP TABLE users")
        assert df is None
        assert not result.success
        assert "validation failed" in (result.error or "").lower()

    def test_rejects_empty_sql(self, mock_db, config):
        svc = QueryService(mock_db, config)
        df, result = svc.execute("")
        assert df is None
        assert not result.success

    def test_success_path(self, mock_db, config):
        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_result.keys.return_value = ["id", "name"]
        mock_result.fetchall.return_value = [(1, "Alice"), (2, "Bob")]

        mock_db.engine.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_db.engine.connect.return_value.__exit__ = MagicMock(return_value=False)
        mock_conn.execute.return_value = mock_result

        svc = QueryService(mock_db, config)
        df, result = svc.execute("SELECT id, name FROM users")

        assert result.success
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 2
        assert list(df.columns) == ["id", "name"]

    def test_handles_db_exception(self, mock_db, config):
        mock_db.engine.connect.return_value.__enter__ = MagicMock(
            side_effect=RuntimeError("connection lost")
        )
        mock_db.engine.connect.return_value.__exit__ = MagicMock(return_value=False)

        svc = QueryService(mock_db, config)
        df, result = svc.execute("SELECT 1")

        assert df is None
        assert not result.success
        assert "connection lost" in (result.error or "")
