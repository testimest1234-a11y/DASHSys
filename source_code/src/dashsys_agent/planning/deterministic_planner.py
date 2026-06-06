from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from dashsys_agent.nlp.entity_extractor import EntityMatch, extract_entities
from dashsys_agent.planning.candidate_plans import CandidatePlan, candidate_plans_for_intent
from dashsys_agent.planning.intent_router import IntentResult, route_intent


@dataclass(frozen=True)
class PlanResult:
    intent_result: IntentResult
    candidates: list[CandidatePlan]
    selected_plan: CandidatePlan | None
    entities: list[EntityMatch]
    local_llm_calls: int = 0
    warnings: list[str] | None = None

    def metadata(self, query: str) -> dict[str, Any]:
        return {
            "query": query,
            "selected_intent": self.intent_result.intent.value,
            "confidence": self.intent_result.confidence,
            "entities": [entity.to_dict() for entity in self.entities],
            "relevant_schema": {},
            "join_paths": [],
            "candidate_api_endpoints": [
                f"{request.method} {request.path}"
                for plan in self.candidates
                for request in plan.api_requests
            ],
            "selected_plan": self.selected_plan.to_dict() if self.selected_plan else {},
            "router_evidence": self.intent_result.evidence,
            "warnings": self.warnings or [],
        }


def plan_query(query: str, catalog: dict[str, Any] | None = None) -> PlanResult:
    intent_result = route_intent(query)
    candidates = candidate_plans_for_intent(intent_result.intent, query)
    entities = extract_entities(query, catalog)
    selected = candidates[0] if candidates else None
    warnings = [] if selected else ["No candidate plan matched the query."]
    return PlanResult(intent_result, candidates, selected, entities, 0, warnings)
