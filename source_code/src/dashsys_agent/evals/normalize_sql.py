from __future__ import annotations

from typing import Any

import duckdb

from dashsys_agent.sql.validate import execute_sql
from dashsys_agent.utils import normalize_row


def generated_sql_from_trajectory(trajectory: dict[str, Any]) -> str:
    for step in trajectory.get("trace", []):
        if step.get("action") == "sql_query":
            return str(step.get("sql", ""))
    return ""


def normalized_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [normalize_row(row) for row in rows]


def execute_for_compare(con: duckdb.DuckDBPyConnection, sql: str, max_rows: int) -> tuple[bool, list[dict[str, Any]], str]:
    if not sql.strip():
        return True, [], "no SQL"
    validation, rows = execute_sql(con, sql, max_rows=max_rows)
    if not validation.valid:
        return False, [], validation.error or "SQL failed"
    return True, normalized_rows(rows), "ok"
