from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import urlparse

from dashsys_agent.api.catalog import ApiRequest

API_UNAVAILABLE_DUE_TO_ENTITY_STATE = "API_UNAVAILABLE_DUE_TO_ENTITY_STATE"

_STATE_LIMITED_BATCH_STATES = {"inactive", "archived", "expired", "deleted", "disabled"}
_UNAVAILABLE_MESSAGE_HINTS = (
    "inactive",
    "not found in catalog",
    "not available",
    "expected batch statuses",
    "not listable",
)


def _record_path(record: dict[str, Any]) -> str:
    endpoint_path = record.get("endpoint_path")
    if isinstance(endpoint_path, str) and endpoint_path:
        return endpoint_path
    url = str(record.get("url", ""))
    parsed = urlparse(url)
    return parsed.path if parsed.scheme else url


def _batch_id_from_export_path(path: str) -> str | None:
    match = re.fullmatch(r"/data/foundation/export/batches/([^/]+)/(files|failed|meta)", path)
    return match.group(1) if match else None


def _catalog_batch_payload(record: dict[str, Any], batch_id: str) -> dict[str, Any] | None:
    preview = record.get("result_preview")
    if not isinstance(preview, dict):
        return None
    direct = preview.get(batch_id)
    if isinstance(direct, dict):
        return direct
    if len(preview) == 1:
        only_value = next(iter(preview.values()))
        if isinstance(only_value, dict):
            return only_value
    return None


def _text_contains_unavailable_hint(record: dict[str, Any]) -> bool:
    text = json.dumps(record.get("result_preview", ""), sort_keys=True, default=str)
    if record.get("message"):
        text += " " + str(record["message"])
    text = text.lower()
    return any(hint in text for hint in _UNAVAILABLE_MESSAGE_HINTS)


def supporting_catalog_request_for_api_failure(record: dict[str, Any]) -> ApiRequest | None:
    """Return a narrow Catalog lookup that can explain a failed batch Data Access call."""

    status_code = record.get("status_code")
    if not isinstance(status_code, int) or status_code < 400:
        return None
    batch_id = _batch_id_from_export_path(_record_path(record))
    if not batch_id:
        return None
    return ApiRequest("GET", f"/data/foundation/catalog/batches/{batch_id}", {})


def classify_entity_state_edge_case(
    failed_record: dict[str, Any],
    supporting_record: dict[str, Any],
) -> dict[str, Any] | None:
    status_code = failed_record.get("status_code")
    if not isinstance(status_code, int) or status_code < 400:
        return None
    batch_id = _batch_id_from_export_path(_record_path(failed_record))
    if not batch_id:
        return None
    if supporting_record.get("status_code") != 200:
        return None
    supporting_path = _record_path(supporting_record)
    expected_support_path = f"/data/foundation/catalog/batches/{batch_id}"
    if supporting_path != expected_support_path:
        return None
    batch = _catalog_batch_payload(supporting_record, batch_id)
    if not batch:
        return None
    state = str(batch.get("status", "")).lower()
    if state not in _STATE_LIMITED_BATCH_STATES:
        return None
    if not _text_contains_unavailable_hint(failed_record):
        return None
    return {
        "category": API_UNAVAILABLE_DUE_TO_ENTITY_STATE,
        "entity_type": "batch",
        "entity_id": batch_id,
        "entity_state": state,
        "primary_endpoint_path": _record_path(failed_record),
        "primary_status_code": status_code,
        "supporting_endpoint_path": supporting_path,
        "supporting_status_code": supporting_record.get("status_code"),
        "conclusion": (
            "The batch exists in Catalog, but its state prevents the requested "
            "Data Access or diagnostics operation from being listed."
        ),
    }
