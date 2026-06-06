from __future__ import annotations

from rapidfuzz import fuzz


def score_answer(gold_answer: str, predicted_answer: str, sql_pass: bool, api_pass: bool) -> tuple[bool, float, str]:
    if sql_pass and api_pass and predicted_answer.strip():
        return True, 1.0, "Evidence checks passed"
    similarity = fuzz.token_set_ratio(gold_answer, predicted_answer) / 100.0
    if similarity >= 0.75:
        return True, similarity, "Answer text similarity passed"
    return False, similarity, f"Answer evidence coverage failed with similarity={similarity:.2f}"
