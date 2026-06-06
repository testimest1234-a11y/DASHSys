from __future__ import annotations

from dashsys_agent.llm.lmstudio_client import LmStudioClient
from dashsys_agent.planning.candidate_plans import CandidatePlan


def maybe_select_plan_with_llm(
    client: LmStudioClient,
    query: str,
    candidates: list[CandidatePlan],
    confidence: float,
) -> tuple[CandidatePlan | None, int]:
    if confidence >= 0.7 or len(candidates) <= 1 or not client.available():
        return (candidates[0] if candidates else None, 0)
    selected_id = client.select_plan(query, [candidate.to_dict() for candidate in candidates])
    for candidate in candidates:
        if candidate.id == selected_id:
            return candidate, 1
    return (candidates[0] if candidates else None, 1)
