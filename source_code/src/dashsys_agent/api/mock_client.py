from __future__ import annotations

import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from dashsys_agent.api.catalog import ApiCatalog, ApiRequest, fixture_key, parse_api_call_spec
from dashsys_agent.api.client_base import ApiResult
from dashsys_agent.api.sanitize import redact_payload
from dashsys_agent.config import Settings
from dashsys_agent.utils import read_json, write_json


def _path_from_url(url: str) -> str:
    return urlparse(url).path if "://" in url else url


def _response_from_trace_call(call: dict[str, Any]) -> dict[str, Any]:
    try:
        status_code = int(call.get("status_code", 200))
    except (TypeError, ValueError):
        status_code = 200
    return {
        "status_code": status_code,
        "result_preview": call.get("result_preview", []),
        "total": call.get("total", 0),
        "answer": call.get("answer"),
        "mock": True,
    }


def extract_fixtures_from_samples(samples_path: Path, fixtures_path: Path) -> dict[str, Any]:
    samples = read_json(samples_path)
    fixtures: dict[str, Any] = {}
    for sample in samples:
        trace_calls = [
            step.get("api_call", {})
            for step in sample.get("trace", [])
            if step.get("action") == "api_call"
        ]
        for call in trace_calls:
            path = _path_from_url(str(call.get("url", "")))
            key = fixture_key(str(call.get("method", "GET")), path, call.get("params", {}), call.get("body"))
            fixtures[key] = {
                "key": key,
                "method": str(call.get("method", "GET")).upper(),
                "path": path,
                "params": call.get("params", {}),
                "body": call.get("body"),
                "response": _response_from_trace_call(call),
            }
        for idx, spec in enumerate(sample.get("gold_api") or []):
            request = parse_api_call_spec(spec)
            response = _response_from_trace_call(trace_calls[min(idx, len(trace_calls) - 1)]) if trace_calls else {
                "status_code": 200,
                "result_preview": [],
                "total": 0,
                "answer": sample.get("answer"),
                "mock": True,
            }
            key = fixture_key(request.method, request.path, request.params, request.body)
            fixtures[key] = {
                "key": key,
                "method": request.method,
                "path": request.path,
                "params": request.params,
                "body": request.body,
                "response": response,
            }
    write_json(fixtures_path, {"fixtures": fixtures})
    return fixtures


class MockApiClient:
    def __init__(self, settings: Settings, catalog: ApiCatalog | None = None) -> None:
        self.settings = settings
        self.catalog = catalog or ApiCatalog.load()
        self.fixtures_path = settings.repo_root / "data" / "mock_api" / "fixtures.json"
        if self.fixtures_path.exists():
            self.fixtures = read_json(self.fixtures_path).get("fixtures", {})
            for fixture in list(self.fixtures.values()):
                alias = fixture_key(
                    fixture.get("method", "GET"),
                    fixture.get("path", ""),
                    fixture.get("params", {}),
                    fixture.get("body"),
                )
                self.fixtures.setdefault(alias, fixture)
        else:
            self.fixtures = extract_fixtures_from_samples(settings.samples_path, self.fixtures_path)
        self.fixture_hits = 0
        self.fixture_misses = 0
        self.whitelist_rejections = 0

    def call(
        self,
        method: str,
        url: str,
        params: dict[str, Any] | None = None,
        headers: dict[str, Any] | None = None,
        body: Any | None = None,
    ) -> ApiResult:
        started = time.perf_counter()
        del headers
        params = params or {}
        path = _path_from_url(url)
        request = ApiRequest(method=method.upper(), path=path, params=params, body=body)
        validation = self.catalog.validate(request)
        if not validation.valid:
            self.whitelist_rejections += 1
            return ApiResult(
                method=method.upper(),
                url=f"{self.settings.adobe_base_url}{path}",
                params=params,
                body=body,
                status_code=400,
                result_preview=[],
                total=0,
                mock=True,
                mock_fixture_miss=True,
                message=validation.error,
                endpoint_path=path,
                latency_seconds=time.perf_counter() - started,
                error_category="api_whitelist_rejection",
            )
        key = fixture_key(method, path, params, body)
        fixture = self.fixtures.get(key)
        if fixture:
            self.fixture_hits += 1
            response = redact_payload(fixture["response"], self.settings)
            return ApiResult(
                method=method.upper(),
                url=f"{self.settings.adobe_base_url}{path}",
                params=params,
                body=body,
                status_code=int(response.get("status_code", 200)),
                result_preview=response.get("result_preview", []),
                total=response.get("total", 0),
                mock=True,
                message=response.get("answer"),
                endpoint_path=path,
                latency_seconds=time.perf_counter() - started,
                error_category="none",
            )
        self.fixture_misses += 1
        return ApiResult(
            method=method.upper(),
            url=f"{self.settings.adobe_base_url}{path}",
            params=params,
            body=body,
            status_code=200,
            result_preview=[],
            total=0,
            mock=True,
            mock_fixture_miss=True,
            message="No mock fixture matched this API call.",
            endpoint_path=path,
            latency_seconds=time.perf_counter() - started,
            error_category="mock_fixture_miss",
        )
