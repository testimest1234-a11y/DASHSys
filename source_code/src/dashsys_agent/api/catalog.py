from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlparse

import yaml

from dashsys_agent.paths import repo_root


@dataclass(frozen=True)
class ApiRequest:
    method: str
    path: str
    params: dict[str, Any]
    body: Any | None = None

    @property
    def url(self) -> str:
        return f"https://platform.adobe.io{self.path}"


@dataclass(frozen=True)
class EndpointSpec:
    name: str
    method: str
    path: str
    allowed_params: tuple[str, ...]
    allowed_body: bool = False
    description: str = ""

    def path_matches(self, path: str) -> bool:
        pattern = re.escape(self.path)
        pattern = re.sub(r"\\\{[^}]+\\\}", r"[^/]+", pattern)
        return re.fullmatch(pattern, path) is not None


@dataclass(frozen=True)
class ApiValidationResult:
    valid: bool
    endpoint: str | None = None
    error: str | None = None


class ApiCatalog:
    def __init__(self, endpoints: list[EndpointSpec]) -> None:
        self.endpoints = endpoints

    @classmethod
    def load(cls, path: Path | None = None) -> ApiCatalog:
        path = path or repo_root() / "configs" / "api_catalog.yml"
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        endpoints = []
        for name, spec in payload.get("endpoints", {}).items():
            endpoints.append(
                EndpointSpec(
                    name=name,
                    method=str(spec["method"]).upper(),
                    path=str(spec["path"]),
                    allowed_params=tuple(spec.get("allowed_params", [])),
                    allowed_body=bool(spec.get("allowed_body", False)),
                    description=str(spec.get("description", "")),
                )
            )
        return cls(endpoints)

    def validate(self, request: ApiRequest) -> ApiValidationResult:
        for endpoint in self.endpoints:
            if endpoint.method != request.method.upper():
                continue
            if not endpoint.path_matches(request.path):
                continue
            extra = set(request.params) - set(endpoint.allowed_params)
            if extra:
                return ApiValidationResult(False, endpoint.name, f"Unexpected API params: {sorted(extra)}")
            if request.body is not None and not endpoint.allowed_body:
                return ApiValidationResult(False, endpoint.name, "Endpoint does not allow a request body")
            return ApiValidationResult(True, endpoint.name, None)
        return ApiValidationResult(False, None, f"Endpoint is not whitelisted: {request.method} {request.path}")


def parse_api_call_spec(spec: str) -> ApiRequest:
    method, rest = spec.strip().split(" ", 1)
    method = method.upper()
    body = None
    if " body=" in rest:
        rest, body_text = rest.split(" body=", 1)
        try:
            body = json.loads(body_text)
        except json.JSONDecodeError:
            body = body_text
    parsed = urlparse(rest)
    path = parsed.path or rest.split("?", 1)[0]
    params = dict(parse_qsl(parsed.query, keep_blank_values=True))
    return ApiRequest(method=method, path=path, params=params, body=body)


def normalize_param_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (int, float, bool)):
        return str(value).lower() if isinstance(value, bool) else str(value)
    text = str(value)
    return re.sub(r"\b[A-Fa-f0-9]{20,}@AdobeOrg\b", "<ims_org>", text)


def fixture_key(method: str, path: str, params: dict[str, Any] | None = None, body: Any | None = None) -> str:
    params = params or {}
    query = "&".join(f"{key}={normalize_param_value(params[key])}" for key in sorted(params))
    key = f"{method.upper()} {path}"
    if query:
        key += f"?{query}"
    if body is not None:
        key += " body=" + json.dumps(body, sort_keys=True, separators=(",", ":"))
    return key
