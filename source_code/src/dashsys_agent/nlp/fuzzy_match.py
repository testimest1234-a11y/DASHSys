from __future__ import annotations

from dataclasses import dataclass

from rapidfuzz import fuzz, process


@dataclass(frozen=True)
class FuzzyMatch:
    value: str
    score: float


def best_match(query: str, choices: list[str]) -> FuzzyMatch | None:
    if not choices:
        return None
    result = process.extractOne(query, choices, scorer=fuzz.WRatio)
    if not result:
        return None
    value, score, _ = result
    return FuzzyMatch(value=str(value), score=float(score))
