from __future__ import annotations

import re


def rewrite_dateadd_for_duckdb(sql: str) -> str:
    sql = re.sub(
        r"DATEADD\s*\(\s*MONTH\s*,\s*(-?\d+)\s*,\s*CURRENT_DATE\s*\)",
        lambda m: f"CURRENT_DATE {'-' if int(m.group(1)) < 0 else '+'} INTERVAL '{abs(int(m.group(1)))} months'",
        sql,
        flags=re.IGNORECASE,
    )
    sql = re.sub(
        r"DATEADD\s*\(\s*DAY\s*,\s*(-?\d+)\s*,\s*CURRENT_DATE\s*\)",
        lambda m: f"CURRENT_DATE {'-' if int(m.group(1)) < 0 else '+'} INTERVAL '{abs(int(m.group(1)))} days'",
        sql,
        flags=re.IGNORECASE,
    )
    sql = re.sub(
        r"\bD\.createdTime\s*>=",
        "TRY_CAST(D.createdTime AS TIMESTAMP) >=",
        sql,
        flags=re.IGNORECASE,
    )
    sql = re.sub(
        r"\bD\.UPDATEDTIME\s*>=",
        "TRY_CAST(D.UPDATEDTIME AS TIMESTAMP) >=",
        sql,
        flags=re.IGNORECASE,
    )
    return sql
