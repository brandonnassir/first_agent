"""Tests for the schema service module."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.config import AppConfig
from app.models import ColumnMeta, ForeignKeyMeta, TableMeta
from app.schema_service import SchemaService


@pytest.fixture()
def mock_db():
    db = MagicMock()
    db.get_column_metadata.return_value = [
        {"column_name": "id", "data_type": "integer", "is_nullable": False, "column_default": None},
        {"column_name": "name", "data_type": "character varying", "is_nullable": True, "column_default": None},
    ]
    db.get_primary_keys.return_value = ["id"]
    db.get_foreign_keys.return_value = []
    db.get_row_count_estimate.return_value = 42
    db.fetch_sample_rows.return_value = [
        {"id": 1, "name": "Alice"},
        {"id": 2, "name": "Bob"},
    ]
    return db


@pytest.fixture()
def config():
    return AppConfig()


class TestGetTableMeta:
    def test_returns_table_meta(self, mock_db, config):
        svc = SchemaService(mock_db, config)
        meta = svc.get_table_meta("public", "users")

        assert isinstance(meta, TableMeta)
        assert meta.schema_name == "public"
        assert meta.table_name == "users"
        assert len(meta.columns) == 2
        assert meta.columns[0].is_primary_key is True
        assert meta.columns[1].is_primary_key is False
        assert meta.row_count_estimate == 42

    def test_sample_values_populated(self, mock_db, config):
        svc = SchemaService(mock_db, config)
        meta = svc.get_table_meta("public", "users")
        assert meta.columns[0].sample_values == [1, 2]
        assert meta.columns[1].sample_values == ["Alice", "Bob"]


class TestBuildSchemaContext:
    def test_returns_list_of_dicts(self, mock_db, config):
        svc = SchemaService(mock_db, config)
        ctx = svc.build_schema_context([("public", "users")])
        assert isinstance(ctx, list)
        assert len(ctx) == 1
        assert ctx[0]["schema_name"] == "public"

    def test_handles_metadata_failure(self, mock_db, config):
        mock_db.get_column_metadata.side_effect = RuntimeError("boom")
        svc = SchemaService(mock_db, config)
        ctx = svc.build_schema_context([("public", "broken")])
        assert len(ctx) == 1
        assert "error" in ctx[0]
