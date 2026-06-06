from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import duckdb
import sqlglot

from dashsys_agent.sql.repair import rewrite_dateadd_for_duckdb
from dashsys_agent.utils import to_jsonable

FORBIDDEN = re.compile(r"\b(INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|COPY|ATTACH|INSTALL|LOAD|PRAGMA)\b", re.IGNORECASE)


@dataclass(frozen=True)
class SqlValidationResult:
    valid: bool
    sql: str
    row_count: int
    columns: list[str]
    error: str | None = None


def validate_sql(con: duckdb.DuckDBPyConnection, sql: str, max_rows: int = 500) -> SqlValidationResult:
    candidate = rewrite_dateadd_for_duckdb(sql.strip().rstrip(";"))
    if FORBIDDEN.search(candidate):
        return SqlValidationResult(False, candidate, 0, [], "Forbidden SQL keyword")
    try:
        statements = sqlglot.parse(candidate, read="duckdb")
    except Exception as exc:
        return SqlValidationResult(False, candidate, 0, [], f"SQL parse error: {exc}")
    if len(statements) != 1:
        return SqlValidationResult(False, candidate, 0, [], "SQL must contain exactly one statement")
    if statements[0].key.upper() != "SELECT":
        return SqlValidationResult(False, candidate, 0, [], "SQL must be SELECT only")
    try:
        preview_sql = f"SELECT * FROM ({candidate}) AS generated_query LIMIT {max_rows}"
        result = con.execute(preview_sql)
        columns = [desc[0] for desc in result.description]
        rows = result.fetchall()
        return SqlValidationResult(True, candidate, len(rows), columns, None)
    except Exception as exc:
        return SqlValidationResult(False, candidate, 0, [], f"DuckDB validation error: {exc}")


def execute_sql(con: duckdb.DuckDBPyConnection, sql: str, max_rows: int = 500) -> tuple[SqlValidationResult, list[dict[str, Any]]]:
    validation = validate_sql(con, sql, max_rows=max_rows)
    if not validation.valid:
        return validation, []
    result = con.execute(f"SELECT * FROM ({validation.sql}) AS generated_query LIMIT {max_rows}")
    columns = [desc[0] for desc in result.description]
    rows = [dict(zip(columns, to_jsonable(row), strict=False)) for row in result.fetchall()]
    return validation, rows
