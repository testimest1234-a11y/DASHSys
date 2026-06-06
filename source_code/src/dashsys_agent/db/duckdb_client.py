from __future__ import annotations

from dataclasses import dataclass

import duckdb

from dashsys_agent.config import Settings
from dashsys_agent.db.parquet_loader import register_parquet_views


@dataclass
class DuckDbClient:
    settings: Settings
    con: duckdb.DuckDBPyConnection
    tables: list[str]

    @classmethod
    def connect(cls, settings: Settings) -> DuckDbClient:
        con = duckdb.connect(database=":memory:")
        tables = register_parquet_views(con, settings.snapshot_dir)
        return cls(settings=settings, con=con, tables=tables)

    def close(self) -> None:
        self.con.close()
