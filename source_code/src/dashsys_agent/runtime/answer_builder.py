from __future__ import annotations

from typing import Any

from dashsys_agent.planning.intent_router import Intent
from dashsys_agent.runtime.evidence import EvidenceBundle


def _edge_case_answer(evidence: EvidenceBundle) -> str | None:
    for record in evidence.api_records:
        edge = record.get("edge_case_evidence")
        if not isinstance(edge, dict):
            continue
        if edge.get("category") != "API_UNAVAILABLE_DUE_TO_ENTITY_STATE":
            continue
        if edge.get("entity_type") == "batch":
            batch_id = edge.get("entity_id")
            state = edge.get("entity_state")
            return (
                f"Batch {batch_id} exists in Catalog, but it is {state}. "
                "Because of this state, failed-file retrieval is not available through the Data Access API. "
                "Therefore, the system cannot list failed files for this batch; this is an expected "
                "entity-state limitation rather than a missing batch."
            )
    return None


def _display_value(row: dict[str, Any]) -> str:
    preferred = [
        "campaign_name",
        "CAMPAIGNNAME",
        "segment_name",
        "collection_name",
        "blueprint_name",
        "target_name",
        "property_name",
        "dataflow_name",
    ]
    for key in preferred:
        if key in row and row[key] not in (None, ""):
            return str(row[key])
    if row:
        first_key = next(iter(row))
        return str(row[first_key])
    return ""


def build_answer(query: str, intent: Intent, evidence: EvidenceBundle) -> str:
    del query
    if intent == Intent.BATCH_FAILED_FILES:
        edge_answer = _edge_case_answer(evidence)
        if edge_answer:
            return edge_answer

    parts: list[str] = []
    if evidence.sql_rows:
        names = [_display_value(row) for row in evidence.sql_rows[:5]]
        names = [name for name in names if name]
        if names:
            parts.append(f"SQL evidence returned {len(evidence.sql_rows)} row(s): {', '.join(names)}.")
        else:
            parts.append(f"SQL evidence returned {len(evidence.sql_rows)} row(s).")
    elif any(record for record in evidence.api_records):
        parts.append("SQL evidence was not required or returned no rows.")
    else:
        parts.append("No SQL evidence was available.")

    api_messages = [record.get("message") for record in evidence.api_records if record.get("message")]
    fixture_misses = [record for record in evidence.api_records if record.get("mock_fixture_miss")]
    if api_messages:
        parts.append(f"API evidence: {api_messages[0]}")
    elif evidence.api_records:
        totals = [record.get("total") for record in evidence.api_records if record.get("total") is not None]
        if totals:
            parts.append(f"API evidence returned totals: {', '.join(str(total) for total in totals)}.")
        else:
            parts.append(f"API evidence includes {len(evidence.api_records)} call(s).")
    if fixture_misses:
        parts.append("One or more mock API fixtures were missing.")
    if evidence.errors:
        parts.append(f"Errors: {'; '.join(evidence.errors)}.")
    if not parts:
        return f"Evidence is insufficient for intent {intent.value}."
    return " ".join(parts)
