from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from dashsys_agent.nlp.normalize import normalize_query


class Intent(str, Enum):
    LIST_JOURNEYS = "list_journeys"
    INACTIVE_JOURNEYS = "inactive_journeys"
    JOURNEY_PUBLISHED_TIME = "journey_published_time"
    SEGMENTS_FOR_DESTINATION = "segments_for_destination"
    FAILED_DATAFLOW_RUNS = "failed_dataflow_runs"
    EXPORT_DESTINATIONS = "export_destinations"
    DATASETS_SAME_SCHEMA = "datasets_same_schema"
    DATASETS_FOR_SCHEMA = "datasets_for_schema"
    PROPERTIES_FOR_SEGMENT = "properties_for_segment"
    SCHEMA_DETAILS = "schema_details"
    EXPERIENCE_EVENT_PROFILE_SCHEMA_COUNT = "experience_event_profile_schema_count"
    SCHEMA_COUNT = "schema_count"
    RECENT_AUDIENCE_DESTINATION_MAPPINGS = "recent_audience_destination_mappings"
    RECENT_DATASET_CHANGES = "recent_dataset_changes"
    ENTITIES_CREATED_BY = "entities_created_by"
    DUPLICATE_AUDIENCE_GROUPS = "duplicate_audience_groups"
    DUPLICATE_AUDIENCE_COUNT = "duplicate_audience_count"
    AUDIENCE_MULTI_JOURNEY_CHECK = "audience_multi_journey_check"
    AUDIENCES_IN_MULTIPLE_JOURNEYS = "audiences_in_multiple_journeys"
    AUDIENCES_FOR_LIVE_JOURNEY_KEYWORD = "audiences_for_live_journey_keyword"
    AUDIENCES_UNMAPPED_UNUSED = "audiences_unmapped_unused"
    AUDIENCE_PROFILE_SUMMARY = "audience_profile_summary"
    SCHEMA_PROPERTIES_FOR_LIVE_JOURNEY_AUDIENCES = "schema_properties_for_live_journey_audiences"
    UNREFERENCED_PROPERTIES = "unreferenced_properties"
    TAG_COUNT = "tag_count"
    LIST_TAGS = "list_tags"
    TAGS_FOR_CATEGORY = "tags_for_category"
    TAG_DETAILS = "tag_details"
    LIST_MERGE_POLICIES = "list_merge_policies"
    MERGE_POLICY_COUNT = "merge_policy_count"
    DEFAULT_MERGE_POLICY = "default_merge_policy"
    SEGMENT_DEFINITION_COUNT = "segment_definition_count"
    LIST_SEGMENT_DEFINITIONS = "list_segment_definitions"
    RECENT_SEGMENT_DEFINITIONS = "recent_segment_definitions"
    LIST_SEGMENT_JOBS = "list_segment_jobs"
    SEGMENT_JOBS_BY_STATUS = "segment_jobs_by_status"
    PROCESSING_SEGMENT_JOBS = "processing_segment_jobs"
    QUEUED_SEGMENT_JOBS = "queued_segment_jobs"
    RECENT_BATCHES = "recent_batches"
    BATCH_SUCCESS_COUNT = "batch_success_count"
    BATCH_DETAILS = "batch_details"
    BATCH_FILES = "batch_files"
    BATCH_FAILED_FILES = "batch_failed_files"
    OBSERVABILITY_DAILY_METRIC = "observability_daily_metric"
    OBSERVABILITY_DAILY_RECORD_SUCCESS = "observability_daily_record_success"
    OBSERVABILITY_INGESTION_COUNTS = "observability_ingestion_counts"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class IntentResult:
    intent: Intent
    confidence: float
    evidence: list[str]


def route_intent(query: str) -> IntentResult:
    q = normalize_query(query)
    evidence: list[str] = []

    def hit(intent: Intent, confidence: float, *why: str) -> IntentResult:
        return IntentResult(intent=intent, confidence=confidence, evidence=list(why))

    if "published" in q and ("journey" in q or "campaign" in q):
        return hit(Intent.JOURNEY_PUBLISHED_TIME, 0.95, "published", "journey")
    if ("inactive" in q or "not live" in q or "not active" in q) and (
        "journey" in q or "campaign" in q
    ):
        return hit(Intent.INACTIVE_JOURNEYS, 0.95, "inactive", "journey")
    if (
        "list all journeys" in q
        or q == "list journeys"
        or "show every journey" in q
        or "show all campaigns" in q
        or "list campaigns" in q
    ):
        return hit(Intent.LIST_JOURNEYS, 0.95, "list", "journeys")
    if "not mapped to any destination" in q and "not used in any journey" in q:
        return hit(Intent.AUDIENCES_UNMAPPED_UNUSED, 0.95, "audience", "unmapped", "unused")
    if "audience" in q and "destination" in q and (
        "connected" in q or "mapped" in q or "use" in q or "using" in q
    ):
        if "last 3 months" in q or "last three months" in q:
            return hit(Intent.RECENT_AUDIENCE_DESTINATION_MAPPINGS, 0.9, "audience", "destination", "recent")
        return hit(Intent.SEGMENTS_FOR_DESTINATION, 0.92, "audience", "destination")
    if "failed dataflow" in q:
        return hit(Intent.FAILED_DATAFLOW_RUNS, 0.92, "failed dataflow")
    if "all destinations" in q or ("destination" in q and "sorted by most recently modified" in q):
        return hit(Intent.EXPORT_DESTINATIONS, 0.9, "destinations")
    if "same schema" in q and "dataset" in q:
        return hit(Intent.DATASETS_SAME_SCHEMA, 0.9, "dataset", "same schema")
    if "datasets" in q and ("use the schema" in q or "for schema" in q or "using schema" in q):
        return hit(Intent.DATASETS_FOR_SCHEMA, 0.92, "datasets", "schema")
    if "field for" in q or "fields used by" in q or "properties for segment" in q:
        return hit(Intent.PROPERTIES_FOR_SEGMENT, 0.9, "field for")
    if "details for the schema" in q or "more details for the schema" in q:
        return hit(Intent.SCHEMA_DETAILS, 0.9, "schema details")
    if "experience event" in q and "profile" in q:
        return hit(Intent.EXPERIENCE_EVENT_PROFILE_SCHEMA_COUNT, 0.9, "experience event", "profile")
    if "how many schemas" in q:
        return hit(Intent.SCHEMA_COUNT, 0.95, "schema count")
    if "recent changes in datasets" in q or "datasets changed recently" in q:
        return hit(Intent.RECENT_DATASET_CHANGES, 0.9, "recent dataset changes")
    if "created by " in q:
        return hit(Intent.ENTITIES_CREATED_BY, 0.9, "created by")
    if "identical rule definitions" in q or "same logic but different names" in q:
        return hit(Intent.DUPLICATE_AUDIENCE_GROUPS, 0.95, "duplicate audience rules")
    if "duplicate audiences" in q:
        return hit(Intent.DUPLICATE_AUDIENCE_COUNT, 0.95, "duplicate audiences")
    if "referenced in more than one journey" in q and "audience" in q:
        return hit(Intent.AUDIENCE_MULTI_JOURNEY_CHECK, 0.95, "audience", "multi journey")
    if "audiences used by live journeys" in q:
        return hit(Intent.AUDIENCES_FOR_LIVE_JOURNEY_KEYWORD, 0.95, "audience", "live journey")
    if "audiences are used in more than one journey" in q:
        return hit(Intent.AUDIENCES_IN_MULTIPLE_JOURNEYS, 0.95, "audience", "multi journey")
    if "what is its profile count" in q and "audience" in q:
        return hit(Intent.AUDIENCE_PROFILE_SUMMARY, 0.95, "audience", "profile count")
    if "properties from the schema" in q and "audiences in live journeys" in q:
        return hit(Intent.SCHEMA_PROPERTIES_FOR_LIVE_JOURNEY_AUDIENCES, 0.95, "schema", "audience properties")
    if "properties not referenced" in q:
        return hit(Intent.UNREFERENCED_PROPERTIES, 0.95, "property references")
    if "tags belong to the category" in q:
        return hit(Intent.TAGS_FOR_CATEGORY, 0.95, "tags", "category")
    if "details of the tag" in q or "tag named" in q:
        return hit(Intent.TAG_DETAILS, 0.95, "tag detail")
    if "how many tags" in q:
        return hit(Intent.TAG_COUNT, 0.95, "tag count")
    if "list all tags" in q:
        return hit(Intent.LIST_TAGS, 0.95, "list tags")
    if "default merge policy" in q:
        return hit(Intent.DEFAULT_MERGE_POLICY, 0.95, "default merge policy")
    if "how many merge policies" in q:
        return hit(Intent.MERGE_POLICY_COUNT, 0.95, "merge policy count")
    if "merge policies" in q:
        return hit(Intent.LIST_MERGE_POLICIES, 0.9, "merge policies")
    if "how many segment definitions" in q:
        return hit(Intent.SEGMENT_DEFINITION_COUNT, 0.95, "segment definition count")
    if "segment definitions" in q and "updated most recently" in q:
        return hit(Intent.RECENT_SEGMENT_DEFINITIONS, 0.95, "segment definitions", "recent")
    if "list all segment definitions" in q:
        return hit(Intent.LIST_SEGMENT_DEFINITIONS, 0.95, "list segment definitions")
    if "segment jobs" in q and "processing" in q:
        return hit(Intent.PROCESSING_SEGMENT_JOBS, 0.95, "segment jobs", "processing")
    if "segment jobs" in q and "queued" in q:
        return hit(Intent.QUEUED_SEGMENT_JOBS, 0.95, "segment jobs", "queued")
    if "segment jobs" in q and ("status" in q or "cancelled" in q or "failed" in q):
        return hit(Intent.SEGMENT_JOBS_BY_STATUS, 0.95, "segment jobs", "status")
    if "segment evaluation jobs" in q:
        return hit(Intent.LIST_SEGMENT_JOBS, 0.95, "segment jobs")
    if "recently created batches" in q:
        return hit(Intent.RECENT_BATCHES, 0.95, "recent batches")
    if "batches have status" in q and "success" in q:
        return hit(Intent.BATCH_SUCCESS_COUNT, 0.95, "batch success")
    if "details of batch" in q:
        return hit(Intent.BATCH_DETAILS, 0.95, "batch detail")
    if "files are available for download" in q and "batch" in q:
        return hit(Intent.BATCH_FILES, 0.95, "batch files")
    if "failed files for batch" in q:
        return hit(Intent.BATCH_FAILED_FILES, 0.95, "batch failed files")
    if "timeseries.ingestion.dataset.recordsuccess.count" in q:
        return hit(Intent.OBSERVABILITY_DAILY_RECORD_SUCCESS, 0.95, "observability metrics")
    if "timeseries.ingestion.dataset." in q:
        return hit(Intent.OBSERVABILITY_DAILY_METRIC, 0.95, "observability metric")
    if "ingestion record counts" in q and "batch success counts" in q:
        return hit(Intent.OBSERVABILITY_INGESTION_COUNTS, 0.95, "observability metrics")
    evidence.append("no deterministic rule matched")
    return IntentResult(intent=Intent.UNKNOWN, confidence=0.0, evidence=evidence)
