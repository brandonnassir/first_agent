"""Tests for the SQL validator module."""

import pytest

from app.sql_validator import maybe_add_limit, validate_sql


class TestValidateSQL:
    """Acceptance and rejection cases for validate_sql."""

    # --- Valid queries ---

    def test_simple_select(self):
        result = validate_sql("SELECT id, name FROM users")
        assert result.is_valid

    def test_select_with_where(self):
        result = validate_sql("SELECT * FROM orders WHERE status = 'active'")
        assert result.is_valid

    def test_with_cte(self):
        sql = (
            "WITH recent AS (SELECT * FROM events WHERE created_at > '2024-01-01') "
            "SELECT * FROM recent"
        )
        result = validate_sql(sql)
        assert result.is_valid

    def test_leading_whitespace(self):
        result = validate_sql("   SELECT 1")
        assert result.is_valid

    def test_trailing_semicolon(self):
        result = validate_sql("SELECT 1;")
        assert result.is_valid

    def test_select_case_insensitive(self):
        result = validate_sql("select id from users")
        assert result.is_valid

    def test_complex_cte(self):
        sql = (
            "WITH a AS (SELECT 1 AS x), "
            "b AS (SELECT x + 1 AS y FROM a) "
            "SELECT * FROM b"
        )
        result = validate_sql(sql)
        assert result.is_valid

    # --- Invalid queries ---

    def test_empty_string(self):
        result = validate_sql("")
        assert not result.is_valid
        assert "Empty" in (result.error or "")

    def test_none(self):
        result = validate_sql(None)
        assert not result.is_valid

    def test_insert(self):
        result = validate_sql("INSERT INTO users (name) VALUES ('bob')")
        assert not result.is_valid

    def test_update(self):
        result = validate_sql("UPDATE users SET name='x'")
        assert not result.is_valid

    def test_delete(self):
        result = validate_sql("DELETE FROM users")
        assert not result.is_valid

    def test_drop_table(self):
        result = validate_sql("DROP TABLE users")
        assert not result.is_valid

    def test_alter_table(self):
        result = validate_sql("ALTER TABLE users ADD COLUMN age int")
        assert not result.is_valid

    def test_truncate(self):
        result = validate_sql("TRUNCATE users")
        assert not result.is_valid

    def test_grant(self):
        result = validate_sql("GRANT ALL ON users TO public")
        assert not result.is_valid

    def test_revoke(self):
        result = validate_sql("REVOKE ALL ON users FROM public")
        assert not result.is_valid

    def test_copy(self):
        result = validate_sql("COPY users TO '/tmp/out.csv'")
        assert not result.is_valid

    def test_create_table(self):
        result = validate_sql("CREATE TABLE evil (id int)")
        assert not result.is_valid

    def test_multiple_statements(self):
        result = validate_sql("SELECT 1; DROP TABLE users")
        assert not result.is_valid
        assert "Multiple" in (result.error or "") or "Dangerous" in (result.error or "")

    def test_dangerous_keyword_in_subquery_still_rejected(self):
        result = validate_sql("SELECT * FROM (DELETE FROM users) AS x")
        assert not result.is_valid

    def test_case_insensitive_dangerous(self):
        result = validate_sql("select * from users; dRoP table users")
        assert not result.is_valid

    def test_dangerous_inside_string_literal_allowed(self):
        result = validate_sql("SELECT * FROM logs WHERE message = 'DELETE event'")
        assert result.is_valid


class TestMaybeAddLimit:
    def test_adds_limit_when_absent(self):
        result = maybe_add_limit("SELECT * FROM users", 100)
        assert "LIMIT 100" in result

    def test_preserves_existing_limit(self):
        sql = "SELECT * FROM users LIMIT 50"
        assert maybe_add_limit(sql, 100) == sql

    def test_skips_aggregate(self):
        sql = "SELECT dept, COUNT(*) FROM users GROUP BY dept"
        assert maybe_add_limit(sql, 100) == sql

    def test_strips_trailing_semicolon(self):
        result = maybe_add_limit("SELECT 1;", 100)
        assert result.endswith("LIMIT 100")
