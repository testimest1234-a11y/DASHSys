from __future__ import annotations

from dataclasses import dataclass

import duckdb

from dashsys_agent.evals.normalize_sql import execute_for_compare, generated_sql_from_trajectory
from dashsys_agent.utils import rows_equal


@dataclass(frozen=True)
class SqlCompareResult:
    exec_success: bool
    result_match: bool
    detail: str


def compare_sql_results(
    con: duckdb.DuckDBPyConnection,
    gold_sql: str,
    trajectory: dict,
    max_rows: int,
) -> SqlCompareResult:
    generated_sql = generated_sql_from_trajectory(trajectory)
    if not gold_sql.strip() and not generated_sql.strip():
        return SqlCompareResult(True, True, "No SQL expected")
    if gold_sql.strip() and not generated_sql.strip():
        return SqlCompareResult(True, False, "Gold SQL exists but generated SQL is missing")
    gen_ok, gen_rows, gen_detail = execute_for_compare(con, generated_sql, max_rows)
    if not gen_ok:
        return SqlCompareResult(False, False, f"Generated SQL failed: {gen_detail}")
    if not gold_sql.strip():
        return SqlCompareResult(True, True, "Generated SQL executed and no gold SQL was required")
    gold_ok, gold_rows, gold_detail = execute_for_compare(con, gold_sql, max_rows)
    if not gold_ok:
        return SqlCompareResult(True, False, f"Gold SQL failed under DuckDB compatibility: {gold_detail}")
    if rows_equal(gen_rows, gold_rows):
        return SqlCompareResult(True, True, "SQL results matched")
    return SqlCompareResult(True, False, f"SQL row mismatch. gold={gold_rows}; generated={gen_rows}")
