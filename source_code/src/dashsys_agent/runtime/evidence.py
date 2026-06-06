from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class EvidenceBundle:
    sql_rows: list[dict[str, Any]] = field(default_factory=list)
    api_records: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "sql_rows": self.sql_rows,
            "api_records": self.api_records,
            "warnings": self.warnings,
            "errors": self.errors,
        }
