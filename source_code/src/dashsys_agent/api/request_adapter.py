from __future__ import annotations

from typing import Any
from urllib.parse import quote

from dashsys_agent.api.catalog import ApiRequest
from dashsys_agent.nlp.entity_extractor import extract_quoted_values

SCHEMA_REGISTRY_PATH = "/data/foundation/schemaregistry/tenant/schemas"
AUDIT_EVENTS_PATH = "/data/foundation/audit/events"
ADOBE_PEAK_SCHEMA_NS = "https://ns.adobe.com/adobepeakprogram/schemas"


def _first_quoted(query: str) -> str:
    values = extract_quoted_values(query)
    return values[0] if values else ""


def _first_schema_ref(payload: Any) -> str | None:
    if isinstance(payload, dict):
        schema_ref = payload.get("schemaRef")
        if isinstance(schema_ref, dict) and schema_ref.get("id"):
            return str(schema_ref["id"])
        schema_id = payload.get("$id")
        if schema_id:
            return str(schema_id)
        for value in payload.values():
            found = _first_schema_ref(value)
            if found:
                return found
    if isinstance(payload, list):
        for item in payload:
            found = _first_schema_ref(item)
            if found:
                return found
    return None


def _schema_ref_from_api_records(api_records: list[dict[str, Any]]) -> str | None:
    for record in reversed(api_records):
        found = _first_schema_ref(record.get("result_preview"))
        if found:
            return found
    return None


def _schema_ref_from_sql_rows(sql_rows: list[dict[str, Any]]) -> str | None:
    for row in sql_rows:
        blueprint_id = row.get("blueprint_id") or row.get("BLUEPRINTID")
        if blueprint_id:
            return f"{ADOBE_PEAK_SCHEMA_NS}/{blueprint_id}"
    return None


def _schema_title_from_sql_rows(sql_rows: list[dict[str, Any]]) -> str | None:
    for row in sql_rows:
        title = row.get("blueprint_name") or row.get("NAME") or row.get("name")
        if title:
            return str(title)
    return None


def _adapt_schema_shortcut(params: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    adapted = dict(params)
    filter_value = adapted.pop("filter", "")
    if isinstance(filter_value, str) and filter_value.startswith("name=="):
        adapted["property"] = "title==" + filter_value.removeprefix("name==")
    return SCHEMA_REGISTRY_PATH, adapted


def adapt_request_for_real_api(
    request: ApiRequest,
    query: str,
    sql_rows: list[dict[str, Any]],
    api_records: list[dict[str, Any]],
) -> ApiRequest:
    """Map sample shorthand requests to the live Adobe API shapes we verified."""

    params = dict(request.params)
    path = request.path

    if path == "/schemas":
        path, params = _adapt_schema_shortcut(params)

    elif path == "/audit/events":
        path = AUDIT_EVENTS_PATH

    elif path == "/data/core/ups/audiences" and params.get("property") == "destinationId==<destination_id>":
        entity = _first_quoted(query)
        params = {"limit": params.get("limit", "5")}
        if entity:
            params["name"] = entity
        else:
            params["property"] = 'audienceId=="<destination_id>"'

    elif path == f"{SCHEMA_REGISTRY_PATH}/{{schema_id}}":
        schema_ref = _schema_ref_from_api_records(api_records) or _schema_ref_from_sql_rows(sql_rows)
        if schema_ref:
            path = f"{SCHEMA_REGISTRY_PATH}/{quote(schema_ref, safe='')}"
            params = {}
        else:
            title = _schema_title_from_sql_rows(sql_rows)
            path = SCHEMA_REGISTRY_PATH
            params = {"limit": "5"}
            if title:
                params["property"] = f"title=={title}"

    elif path.startswith("/data/foundation/export/batches/") and path.endswith("/failed"):
        path = path.removesuffix("/failed") + "/files"
        params = {"status": "failed"}

    return ApiRequest(method=request.method, path=path, params=params, body=request.body)
