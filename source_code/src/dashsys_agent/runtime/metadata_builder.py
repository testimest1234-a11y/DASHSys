from __future__ import annotations

from typing import Any

TABLES_BY_TEMPLATE = {
    "journey_published_time": ["dim_campaign"],
    "inactive_journeys": ["dim_campaign"],
    "list_journeys": ["dim_campaign"],
    "segments_for_destination": ["dim_segment", "hkg_br_segment_target", "dim_target"],
    "failed_dataflow_runs": ["dim_connector"],
    "export_destinations": ["dim_target"],
    "datasets_same_schema": ["dim_collection", "hkg_br_blueprint_collection", "dim_blueprint"],
    "datasets_for_schema": ["hkg_br_blueprint_collection", "dim_collection", "dim_blueprint"],
    "properties_for_segment": ["hkg_br_segment_property", "dim_segment"],
    "schema_details": ["dim_blueprint", "hkg_br_blueprint_collection", "hkg_br_blueprint_property"],
    "experience_event_profile_schema_count": ["dim_blueprint"],
    "schema_count": ["dim_blueprint"],
    "recent_audience_destination_mappings": ["dim_segment", "hkg_br_segment_target", "dim_target"],
    "recent_dataset_changes": ["dim_collection"],
    "entities_created_by": ["dim_collection"],
}


def add_schema_context(metadata: dict[str, Any], catalog: dict[str, Any], join_graph: dict[str, Any]) -> dict[str, Any]:
    selected = metadata.get("selected_plan", {})
    template_id = selected.get("sql_template_id")
    tables = TABLES_BY_TEMPLATE.get(template_id, [])
    metadata["relevant_schema"] = {
        "tables": tables,
        "columns": {
            table: list(catalog.get("tables", {}).get(table, {}).get("columns", {}).keys())
            for table in tables
        },
    }
    joins = []
    for join in join_graph.get("joins", []):
        if join.get("left_table") in tables and join.get("right_table") in tables:
            joins.append(join)
    metadata["join_paths"] = joins
    return metadata
