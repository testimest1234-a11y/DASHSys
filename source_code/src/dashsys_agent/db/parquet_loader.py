from __future__ import annotations

from pathlib import Path

import duckdb


def quote_ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def parquet_files(snapshot_dir: Path) -> list[Path]:
    return sorted(snapshot_dir.glob("*.parquet"))


def register_parquet_views(con: duckdb.DuckDBPyConnection, snapshot_dir: Path) -> list[str]:
    files = parquet_files(snapshot_dir)
    tables: list[str] = []
    for path in files:
        table_name = path.stem
        safe_path = str(path.resolve()).replace("\\", "/").replace("'", "''")
        try:
            con.execute(
                f"CREATE OR REPLACE VIEW {quote_ident(table_name)} AS "
                f"SELECT * FROM read_parquet('{safe_path}')"
            )
        except duckdb.InvalidInputException as exc:
            if "Need at least one non-root column" not in str(exc):
                raise
            con.execute(
                f"CREATE OR REPLACE VIEW {quote_ident(table_name)} AS "
                "SELECT NULL::VARCHAR AS __empty_placeholder WHERE FALSE"
            )
        tables.append(table_name)
    return tables
