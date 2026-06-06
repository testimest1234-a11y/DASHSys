from __future__ import annotations

from typing import Any

import duckdb

from dashsys_agent.db.parquet_loader import quote_ident
from dashsys_agent.utils import to_jsonable

TEXT_TYPES = {"VARCHAR", "TEXT", "STRING"}


def _fetch_dicts(con: duckdb.DuckDBPyConnection, sql: str) -> list[dict[str, Any]]:
    result = con.execute(sql)
    cols = [desc[0] for desc in result.description]
    return [dict(zip(cols, to_jsonable(row), strict=False)) for row in result.fetchall()]


def build_schema_catalog(
    con: duckdb.DuckDBPyConnection,
    tables: list[str],
    sample_rows: int = 3,
    text_samples: int = 10,
) -> dict[str, Any]:
    catalog: dict[str, Any] = {"tables": {}}
    for table in sorted(tables):
        describe_rows = con.execute(f"DESCRIBE SELECT * FROM {quote_ident(table)}").fetchall()
        columns = {str(row[0]): str(row[1]) for row in describe_rows}
        row_count = int(con.execute(f"SELECT COUNT(*) FROM {quote_ident(table)}").fetchone()[0])
        samples = _fetch_dicts(con, f"SELECT * FROM {quote_ident(table)} LIMIT {sample_rows}")
        text_value_samples: dict[str, list[Any]] = {}
        for column, column_type in columns.items():
            if column_type.upper().split("(")[0] not in TEXT_TYPES:
                continue
            rows = con.execute(
                f"SELECT DISTINCT {quote_ident(column)} FROM {quote_ident(table)} "
                f"WHERE {quote_ident(column)} IS NOT NULL LIMIT {text_samples}"
            ).fetchall()
            text_value_samples[column] = [to_jsonable(row[0]) for row in rows]
        catalog["tables"][table] = {
            "columns": columns,
            "row_count": row_count,
            "sample_rows": samples,
            "text_value_samples": text_value_samples,
        }
    return catalog
