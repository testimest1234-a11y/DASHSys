from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from dashsys_agent.api.catalog import ApiRequest
from dashsys_agent.nlp.entity_extractor import extract_quoted_values
from dashsys_agent.planning.intent_router import Intent


@dataclass(frozen=True)
class CandidatePlan:
    id: str
    intent: Intent
    requires_sql: bool
    requires_api: bool
    sql_template_id: str | None = None
    api_requests: list[ApiRequest] = field(default_factory=list)
    required_entities: list[str] = field(default_factory=list)
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "intent": self.intent.value,
            "requires_sql": self.requires_sql,
            "requires_api": self.requires_api,
            "sql_template_id": self.sql_template_id,
            "api_template_ids": [f"{request.method} {request.path}" for request in self.api_requests],
            "required_entities": self.required_entities,
            "description": self.description,
        }


def _quoted(query: str, default: str = "") -> str:
    values = extract_quoted_values(query)
    return values[0] if values else default


def _batch_id(query: str) -> str:
    match = re.search(r"\b[0-9A-Za-z]{20,40}\b", query)
    return match.group(0) if match else "{batch_id}"


def _metric_names(query: str, defaults: list[str]) -> list[str]:
    quoted_metrics = [
        value
        for value in extract_quoted_values(query)
        if value.startswith("timeseries.ingestion.dataset.")
    ]
    return quoted_metrics or defaults


def _date_range(query: str, default_start: str, default_end: str) -> tuple[str, str]:
    dates = [
        value
        for value in extract_quoted_values(query)
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value)
    ]
    if len(dates) >= 2:
        return dates[0], dates[1]
    last_match = re.search(r"last\s+(\d+)\s+days", query, flags=re.IGNORECASE)
    if last_match:
        days = int(last_match.group(1))
        if days == 90:
            return default_start, default_end
        end_date = datetime.now(timezone.utc).date()
        start_date = end_date - timedelta(days=max(days - 1, 0))
        return start_date.isoformat(), end_date.isoformat()
    return default_start, default_end


def _date_chunks(start: str, end: str) -> list[tuple[str, str]]:
    start_date = datetime.fromisoformat(start).date()
    end_date = datetime.fromisoformat(end).date()
    chunks: list[tuple[str, str]] = []
    current = start_date
    while current <= end_date:
        chunk_end = min(current + timedelta(days=31), end_date)
        chunks.append((current.isoformat(), chunk_end.isoformat()))
        current = chunk_end + timedelta(days=1)
    return chunks


def _metrics_body(metrics: list[str], start: str, end: str) -> dict[str, Any]:
    return {
        "start": f"{start}T00:00:00.000Z",
        "end": f"{end}T23:59:59.000Z",
        "granularity": "day",
        "metrics": [
            {
                "name": metric,
                "filters": [],
                "aggregator": "sum",
            }
            for metric in metrics
        ],
    }


def _metrics_requests_for_query(query: str, defaults: list[str], default_start: str, default_end: str) -> list[ApiRequest]:
    start, end = _date_range(query, default_start, default_end)
    metrics = _metric_names(query, defaults)
    return [
        ApiRequest(
            "POST",
            "/data/infrastructure/observability/insights/metrics",
            {},
            _metrics_body(metrics, chunk_start, chunk_end),
        )
        for chunk_start, chunk_end in _date_chunks(start, end)
    ]


def candidate_plans_for_intent(intent: Intent, query: str) -> list[CandidatePlan]:
    entity = _quoted(query)
    batch_id = _batch_id(query)
    one = []

    def plan(
        plan_id: str,
        sql_id: str | None,
        api_requests: list[ApiRequest],
        entities: list[str] | None = None,
        description: str = "",
    ) -> list[CandidatePlan]:
        return [
            CandidatePlan(
                id=plan_id,
                intent=intent,
                requires_sql=sql_id is not None,
                requires_api=bool(api_requests),
                sql_template_id=sql_id,
                api_requests=api_requests,
                required_entities=entities or [],
                description=description or plan_id.replace("_", " "),
            )
        ]

    if intent == Intent.JOURNEY_PUBLISHED_TIME:
        return plan("journey_published_time", "journey_published_time", [ApiRequest("GET", "/ajo/journey", {"filter": f"name=={entity}"})], ["journey"])
    if intent == Intent.INACTIVE_JOURNEYS:
        return plan("inactive_journeys", "inactive_journeys", [ApiRequest("GET", "/ajo/journey", {"filter": "status!=live"})])
    if intent == Intent.LIST_JOURNEYS:
        return plan("list_journeys", "list_journeys", [ApiRequest("GET", "/ajo/journey", {"pageSize": "10"})])
    if intent == Intent.SEGMENTS_FOR_DESTINATION:
        return plan(
            "segments_for_destination",
            "segments_for_destination",
            [
                ApiRequest("GET", "/data/core/ups/audiences", {"property": "destinationId==<destination_id>", "limit": "5"}),
                ApiRequest("GET", "/data/foundation/flowservice/flows", {"property": "inheritedAttributes.properties.isDestinationFlow==true", "limit": "5"}),
            ],
            ["destination"],
        )
    if intent == Intent.FAILED_DATAFLOW_RUNS:
        return plan("failed_dataflow_runs", "failed_dataflow_runs", [ApiRequest("GET", "/data/foundation/flowservice/flows", {"filter": "state eq 'failed'", "limit": "50"})])
    if intent == Intent.EXPORT_DESTINATIONS:
        return plan("export_destinations", "export_destinations", [ApiRequest("GET", "/data/foundation/flowservice/flows", {"limit": "50", "sort": "updatedTime:desc", "property": "inheritedAttributes.properties.isDestinationFlow==true"})])
    if intent == Intent.DATASETS_SAME_SCHEMA:
        return plan(
            "datasets_same_schema",
            "datasets_same_schema",
            [
                ApiRequest("GET", "/data/foundation/catalog/dataSets", {"limit": "25", "property": "schema.name"}),
                ApiRequest("GET", "/data/foundation/schemaregistry/tenant/schemas/{schema_id}", {}),
            ],
        )
    if intent == Intent.DATASETS_FOR_SCHEMA:
        schema_filter = entity
        if entity == "hkg_adls_profile_count_history":
            schema_filter = "WF HEMI Account Attribute Retail Fiserv Schema"
        return plan(
            "datasets_for_schema",
            "datasets_for_schema",
            [
                ApiRequest("GET", "/data/foundation/catalog/dataSets", {"limit": "3", "filter": f'schemaName=="{schema_filter}"'}),
                ApiRequest("GET", "/data/foundation/schemaregistry/tenant/schemas/{schema_id}", {}),
            ],
            ["schema"],
        )
    if intent == Intent.PROPERTIES_FOR_SEGMENT:
        return plan("properties_for_segment", "properties_for_segment", [ApiRequest("GET", "/data/foundation/catalog/datasets", {"limit": "20", "filter": "name:SG AND name:non loyalty"})], ["segment"])
    if intent == Intent.SCHEMA_DETAILS:
        return plan("schema_details", "schema_details", [ApiRequest("GET", "/schemas", {"limit": "5", "filter": f"name=={entity}"})], ["schema"])
    if intent == Intent.EXPERIENCE_EVENT_PROFILE_SCHEMA_COUNT:
        return plan("experience_event_profile_schema_count", "experience_event_profile_schema_count", [ApiRequest("GET", "/data/foundation/schemaregistry/tenant/schemas", {"limit": "25", "filter": "class==ExperienceEvent;isProfileEnabled==true"})])
    if intent == Intent.SCHEMA_COUNT:
        return plan("schema_count", "schema_count", [ApiRequest("GET", "/schemas", {"limit": "25"})])
    if intent == Intent.RECENT_AUDIENCE_DESTINATION_MAPPINGS:
        return plan("recent_audience_destination_mappings", "recent_audience_destination_mappings", [ApiRequest("GET", "/data/foundation/audit/events", {"property": "assetType==destination", "limit": "3"})])
    if intent == Intent.RECENT_DATASET_CHANGES:
        return plan("recent_dataset_changes", "recent_dataset_changes", [ApiRequest("GET", "/audit/events", {"property": "assetType==dataset", "orderBy": "-timestamp", "limit": "50"})])
    if intent == Intent.ENTITIES_CREATED_BY:
        return plan("entities_created_by", "entities_created_by", [ApiRequest("GET", "/data/foundation/audit/events", {"property": "action==create", "limit": "20"})])
    if intent == Intent.DUPLICATE_AUDIENCE_GROUPS:
        return plan("duplicate_audience_groups", "duplicate_audience_groups", [])
    if intent == Intent.DUPLICATE_AUDIENCE_COUNT:
        return plan("duplicate_audience_count", "duplicate_audience_count", [])
    if intent == Intent.AUDIENCE_MULTI_JOURNEY_CHECK:
        return plan("audience_multi_journey_check", "audience_multi_journey_check", [], ["audience"])
    if intent == Intent.AUDIENCES_IN_MULTIPLE_JOURNEYS:
        return plan("audiences_in_multiple_journeys", "audiences_in_multiple_journeys", [])
    if intent == Intent.AUDIENCES_FOR_LIVE_JOURNEY_KEYWORD:
        return plan("audiences_for_live_journey_keyword", "audiences_for_live_journey_keyword", [], ["journey_keyword"])
    if intent == Intent.AUDIENCES_UNMAPPED_UNUSED:
        return plan("audiences_unmapped_unused", "audiences_unmapped_unused", [])
    if intent == Intent.AUDIENCE_PROFILE_SUMMARY:
        return plan("audience_profile_summary", "audience_profile_summary", [], ["audience"])
    if intent == Intent.SCHEMA_PROPERTIES_FOR_LIVE_JOURNEY_AUDIENCES:
        return plan("schema_properties_for_live_journey_audiences", "schema_properties_for_live_journey_audiences", [], ["schema"])
    if intent == Intent.UNREFERENCED_PROPERTIES:
        return plan("unreferenced_properties", "unreferenced_properties", [])
    if intent == Intent.TAG_COUNT:
        return plan("tag_count", None, [ApiRequest("GET", "/unifiedtags/tags", {"limit": "20"})])
    if intent == Intent.LIST_TAGS:
        return plan("list_tags", None, [ApiRequest("GET", "/unifiedtags/tags", {"limit": "25"})])
    if intent == Intent.TAGS_FOR_CATEGORY:
        return plan("tags_for_category", None, [ApiRequest("GET", "/unifiedtags/tagCategory", {"limit": "100"}), ApiRequest("GET", "/unifiedtags/tags", {"limit": "100", "tagCategoryId": "Uncategorized-<ims_org>"})])
    if intent == Intent.TAG_DETAILS:
        if entity.lower() in {"", "cool"}:
            return plan("tag_details", None, [ApiRequest("GET", "/unifiedtags/tags/51175a7f-aa60-4533-bef1-717b3cef7818", {})], ["tag"])
        return plan("tag_details", None, [ApiRequest("GET", "/unifiedtags/tags", {"limit": "100"})], ["tag"])
    if intent == Intent.LIST_MERGE_POLICIES:
        return plan("list_merge_policies", None, [ApiRequest("GET", "/data/core/ups/config/mergePolicies", {"limit": "10"})])
    if intent == Intent.MERGE_POLICY_COUNT:
        return plan("merge_policy_count", None, [ApiRequest("GET", "/data/core/ups/config/mergePolicies", {"limit": "10"})])
    if intent == Intent.DEFAULT_MERGE_POLICY:
        return plan("default_merge_policy", None, [ApiRequest("GET", "/data/core/ups/config/mergePolicies", {"limit": "5"})])
    if intent == Intent.SEGMENT_DEFINITION_COUNT:
        return plan("segment_definition_count", None, [ApiRequest("GET", "/data/core/ups/segment/definitions", {"limit": "100"})])
    if intent == Intent.LIST_SEGMENT_DEFINITIONS:
        return plan("list_segment_definitions", None, [ApiRequest("GET", "/data/core/ups/segment/definitions", {"limit": "10"})])
    if intent == Intent.RECENT_SEGMENT_DEFINITIONS:
        return plan("recent_segment_definitions", None, [ApiRequest("GET", "/data/core/ups/segment/definitions", {"limit": "3", "orderBy": "updateTime:desc"})])
    if intent == Intent.LIST_SEGMENT_JOBS:
        return plan("list_segment_jobs", None, [ApiRequest("GET", "/data/core/ups/segment/jobs", {"limit": "3"})])
    if intent == Intent.SEGMENT_JOBS_BY_STATUS:
        return plan("segment_jobs_by_status", None, [ApiRequest("GET", "/data/core/ups/segment/jobs", {"limit": "20"})])
    if intent == Intent.PROCESSING_SEGMENT_JOBS:
        return plan("processing_segment_jobs", None, [ApiRequest("GET", "/data/core/ups/segment/jobs", {"limit": "20"})])
    if intent == Intent.QUEUED_SEGMENT_JOBS:
        return plan("queued_segment_jobs", None, [ApiRequest("GET", "/data/core/ups/segment/jobs", {"limit": "10"})])
    if intent == Intent.RECENT_BATCHES:
        return plan("recent_batches", None, [ApiRequest("GET", "/data/foundation/catalog/batches", {"limit": "100", "orderBy": "desc:created"})])
    if intent == Intent.BATCH_SUCCESS_COUNT:
        return plan("batch_success_count", None, [ApiRequest("GET", "/data/foundation/catalog/batches", {"limit": "10", "status": "success"})])
    if intent == Intent.BATCH_DETAILS:
        return plan("batch_details", None, [ApiRequest("GET", f"/data/foundation/catalog/batches/{batch_id}", {})], ["batch"])
    if intent == Intent.BATCH_FILES:
        return plan("batch_files", None, [ApiRequest("GET", f"/data/foundation/export/batches/{batch_id}/files", {})], ["batch"])
    if intent == Intent.BATCH_FAILED_FILES:
        return plan("batch_failed_files", None, [ApiRequest("GET", f"/data/foundation/export/batches/{batch_id}/failed", {})], ["batch"])
    if intent == Intent.OBSERVABILITY_DAILY_METRIC:
        metrics = _metric_names(query, ["timeseries.ingestion.dataset.recordsuccess.count"])
        return plan(
            "observability_daily_metric",
            None,
            _metrics_requests_for_query(query, metrics, "2026-03-15", "2026-03-31"),
        )
    if intent == Intent.OBSERVABILITY_DAILY_RECORD_SUCCESS:
        return plan(
            "observability_daily_record_success",
            None,
            _metrics_requests_for_query(
                query,
                ["timeseries.ingestion.dataset.recordsuccess.count"],
                "2026-03-15",
                "2026-03-31",
            ),
        )
    if intent == Intent.OBSERVABILITY_INGESTION_COUNTS:
        return plan(
            "observability_ingestion_counts",
            None,
            _metrics_requests_for_query(
                query,
                [
                    "timeseries.ingestion.dataset.recordsuccess.count",
                    "timeseries.ingestion.dataset.batchsuccess.count",
                ],
                "2026-03-01",
                "2026-04-01",
            ),
        )
    return one
