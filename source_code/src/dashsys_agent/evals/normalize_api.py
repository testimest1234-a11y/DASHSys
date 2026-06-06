from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from dashsys_agent.api.catalog import fixture_key, parse_api_call_spec

SCHEMA_REGISTRY_PATH = "/data/foundation/schemaregistry/tenant/schemas"


def _canonical_request(
    method: str,
    path: str,
    params: dict[str, Any],
    body: Any | None,
) -> tuple[str, str, dict[str, Any], Any | None]:
    method = method.upper()
    params = dict(params or {})
    if method == "GET" and path == "/schemas":
        path = SCHEMA_REGISTRY_PATH
        filter_value = params.pop("filter", "")
        if isinstance(filter_value, str) and filter_value.startswith("name=="):
            params["property"] = "title==" + filter_value.removeprefix("name==")
    if method == "GET" and path.startswith(f"{SCHEMA_REGISTRY_PATH}/"):
        path = f"{SCHEMA_REGISTRY_PATH}/{{schema_id}}"
        params = {}
    if method == "GET" and path == "/audit/events":
        path = "/data/foundation/audit/events"
    if method == "GET" and path == "/data/core/ups/audiences" and "name" in params:
        limit = params.get("limit")
        params = {"property": "destinationId==<destination_id>"}
        if limit is not None:
            params["limit"] = limit
    if method == "GET" and path.startswith("/data/foundation/export/batches/") and path.endswith("/files"):
        if params.get("status") == "failed":
            path = path.removesuffix("/files") + "/failed"
            params = {}
    return method, path, params, body


def normalize_gold_api(specs: list[str]) -> list[str]:
    normalized = []
    for spec in specs:
        request = parse_api_call_spec(spec)
        method, path, params, body = _canonical_request(request.method, request.path, request.params, request.body)
        normalized.append(fixture_key(method, path, params, body))
    return sorted(normalized)


def normalize_generated_api(trajectory: dict[str, Any]) -> list[str]:
    normalized = []
    for step in trajectory.get("trace", []):
        if step.get("action") != "api_call":
            continue
        call = step.get("api_call", {})
        parsed = urlparse(str(call.get("url", "")))
        path = parsed.path if parsed.scheme else str(call.get("url", ""))
        method, canonical_path, params, body = _canonical_request(
            str(call.get("method", "GET")),
            path,
            call.get("params", {}),
            call.get("body"),
        )
        normalized.append(fixture_key(method, canonical_path, params, body))
    return sorted(normalized)


def compare_api(gold_specs: list[str], trajectory: dict[str, Any]) -> tuple[bool, str]:
    gold = normalize_gold_api(gold_specs)
    generated = normalize_generated_api(trajectory)
    if gold == generated:
        return True, "API calls matched"
    return False, f"gold={gold}; generated={generated}"
