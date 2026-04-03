"""SQL validation – ensures only safe read-only queries reach the database."""

from __future__ import annotations

import re

from app.models import SQLValidationResult

DANGEROUS_KEYWORDS: set[str] = {
    "INSERT",
    "UPDATE",
    "DELETE",
    "DROP",
    "ALTER",
    "TRUNCATE",
    "GRANT",
    "REVOKE",
    "COPY",
    "CREATE",
    "EXEC",
    "EXECUTE",
    "CALL",
    "SET",
    "LOCK",
    "VACUUM",
    "REINDEX",
    "CLUSTER",
    "COMMENT",
    "SECURITY",
    "OWNER",
}

_DANGEROUS_PATTERN = re.compile(
    r"\b(" + "|".join(DANGEROUS_KEYWORDS) + r")\b",
    re.IGNORECASE,
)

_COMMENT_LINE = re.compile(r"--.*$", re.MULTILINE)
_COMMENT_BLOCK = re.compile(r"/\*.*?\*/", re.DOTALL)


def validate_sql(sql: str | None) -> SQLValidationResult:
    """Validate a SQL string and return a structured result."""
    if sql is None or not sql.strip():
        return SQLValidationResult(is_valid=False, error="Empty SQL")

    normalized = sql.strip()

    # Reject multiple statements (semicolons not inside string literals)
    without_strings = re.sub(r"'[^']*'", "", normalized)
    semi_count = without_strings.count(";")
    bare = without_strings.rstrip(";").strip()
    if ";" in bare:
        return SQLValidationResult(
            is_valid=False,
            normalized_sql=normalized,
            error="Multiple SQL statements are not allowed",
        )

    stripped_no_comments = _COMMENT_BLOCK.sub("", _COMMENT_LINE.sub("", normalized))
    first_word = stripped_no_comments.strip().split()[0].upper() if stripped_no_comments.strip() else ""

    if first_word not in ("SELECT", "WITH"):
        return SQLValidationResult(
            is_valid=False,
            normalized_sql=normalized,
            error=f"Only SELECT / WITH…SELECT queries are allowed (found '{first_word}')",
        )

    # Scan for dangerous keywords outside string literals and comments
    sql_no_strings = re.sub(r"'[^']*'", "", stripped_no_comments)
    match = _DANGEROUS_PATTERN.search(sql_no_strings)
    if match:
        keyword = match.group(1).upper()
        return SQLValidationResult(
            is_valid=False,
            normalized_sql=normalized,
            error=f"Dangerous keyword detected: {keyword}",
        )

    return SQLValidationResult(is_valid=True, normalized_sql=normalized)


def maybe_add_limit(sql: str, max_rows: int) -> str:
    """Append a LIMIT clause when one is absent and the query does not aggregate."""
    upper = sql.upper()
    if "LIMIT" in upper:
        return sql

    has_agg = any(kw in upper for kw in ("GROUP BY", "COUNT(", "SUM(", "AVG(", "MIN(", "MAX("))
    if has_agg:
        return sql

    clean = sql.rstrip().rstrip(";")
    return f"{clean}\nLIMIT {max_rows}"
