from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from dashsys_agent.nlp.fuzzy_match import best_match
from dashsys_agent.nlp.normalize import normalize_query


@dataclass(frozen=True)
class EntityMatch:
    raw_text: str
    matched_table: str | None = None
    matched_column: str | None = None
    matched_value: str | None = None
    score: float = 0.0
    match_type: str = "literal"

    def to_dict(self) -> dict[str, Any]:
        return {
            "raw_text": self.raw_text,
            "matched_table": self.matched_table,
            "matched_column": self.matched_column,
            "matched_value": self.matched_value,
            "score": self.score,
            "match_type": self.match_type,
        }


def quoted_strings(query: str) -> list[str]:
    return re.findall(r"'([^']+)'|\"([^\"]+)\"", query)


def extract_quoted_values(query: str) -> list[str]:
    values = []
    for left, right in quoted_strings(query):
        values.append(left or right)
    return values


def extract_batch_ids(query: str) -> list[str]:
    return re.findall(r"\b[0-9A-Za-z]{20,40}\b", query)


def build_entity_index(catalog: dict[str, Any]) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    for table, info in catalog.get("tables", {}).items():
        entries.append({"table": table, "column": "", "value": table})
        for column in info.get("columns", {}):
            entries.append({"table": table, "column": column, "value": column})
        for column, values in info.get("text_value_samples", {}).items():
            for value in values:
                if value is not None:
                    entries.append({"table": table, "column": column, "value": str(value)})
    return entries


def extract_entities(query: str, catalog: dict[str, Any] | None = None) -> list[EntityMatch]:
    values = extract_quoted_values(query) + extract_batch_ids(query)
    matches: list[EntityMatch] = []
    if not catalog:
        return [EntityMatch(raw_text=value, matched_value=value, score=100.0) for value in values]
    index = build_entity_index(catalog)
    choices = [entry["value"] for entry in index]
    for value in values:
        exact = next((entry for entry in index if normalize_query(entry["value"]) == normalize_query(value)), None)
        if exact:
            matches.append(
                EntityMatch(
                    raw_text=value,
                    matched_table=exact["table"],
                    matched_column=exact["column"],
                    matched_value=exact["value"],
                    score=100.0,
                    match_type="exact",
                )
            )
            continue
        fuzzy = best_match(value, choices)
        if fuzzy:
            entry = next(entry for entry in index if entry["value"] == fuzzy.value)
            matches.append(
                EntityMatch(
                    raw_text=value,
                    matched_table=entry["table"],
                    matched_column=entry["column"],
                    matched_value=entry["value"],
                    score=fuzzy.score,
                    match_type="fuzzy",
                )
            )
        else:
            matches.append(EntityMatch(raw_text=value, matched_value=value, score=0.0))
    return matches
