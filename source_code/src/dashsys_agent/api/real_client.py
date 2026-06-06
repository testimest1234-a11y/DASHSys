from __future__ import annotations

import time
from typing import Any
from urllib.parse import urlparse

import requests

from dashsys_agent.api.auth import validate_real_api_credentials
from dashsys_agent.api.catalog import ApiCatalog, ApiRequest
from dashsys_agent.api.client_base import ApiResult
from dashsys_agent.api.sanitize import (
    redact_error,
    redact_payload,
    safe_response_summary,
    sanitize_headers,
)
from dashsys_agent.config import Settings


class AdobeAuthError(RuntimeError):
    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.safe_message = message


def _error_category(status_code: int) -> str:
    if status_code in {400, 422}:
        return "params_or_sandbox_validation"
    if status_code in {401, 403}:
        return "auth_or_permission"
    if status_code == 404:
        return "endpoint_or_sandbox_data"
    if status_code == 429 or status_code >= 500:
        return "transient"
    if status_code >= 400:
        return "api_error"
    return "none"


def _base_url_for_path(settings: Settings, path: str) -> str:
    if path.startswith("/unifiedtags/"):
        return "https://experience.adobe.io"
    return settings.adobe_base_url


def _schema_accept_header(path: str) -> str | None:
    schema_path = "/data/foundation/schemaregistry/tenant/schemas"
    if path == schema_path:
        return "application/vnd.adobe.xed-id+json"
    if path.startswith(f"{schema_path}/"):
        return "application/vnd.adobe.xed+json; version=1"
    return None


def _resolve_runtime_placeholders(value: Any, settings: Settings) -> Any:
    if isinstance(value, str):
        return value.replace("<ims_org>", settings.adobe_ims_org)
    if isinstance(value, dict):
        return {key: _resolve_runtime_placeholders(item, settings) for key, item in value.items()}
    if isinstance(value, list):
        return [_resolve_runtime_placeholders(item, settings) for item in value]
    return value


class RealAdobeApiClient:
    def __init__(self, settings: Settings, catalog: ApiCatalog | None = None) -> None:
        if settings.api_mode not in {"real", "record"}:
            raise ValueError("Real Adobe API client is disabled unless API_MODE is real or record")
        if not settings.allow_network:
            raise ValueError("Real Adobe API client requires ALLOW_NETWORK=true")
        missing = validate_real_api_credentials(settings)
        if missing:
            raise ValueError(f"Missing Adobe credentials: {', '.join(missing)}")
        self.settings = settings
        self.catalog = catalog or ApiCatalog.load()
        self._token: str | None = None

    def _get_token(self) -> str:
        if self._token:
            return self._token
        data = {
            "grant_type": "client_credentials",
            "client_id": self.settings.adobe_client_id,
            "client_secret": self.settings.adobe_client_secret,
            "scope": "openid,AdobeID,read_organizations,additional_info.projectedProductContext",
        }
        try:
            response = requests.post(self.settings.adobe_ims_token_url, data=data, timeout=30)
        except requests.RequestException as exc:
            raise AdobeAuthError(0, redact_error(str(exc), self.settings)) from exc
        if response.status_code >= 400:
            summary = safe_response_summary(response.text, self.settings)
            raise AdobeAuthError(response.status_code, summary)
        try:
            token = response.json().get("access_token")
        except ValueError as exc:
            raise AdobeAuthError(response.status_code, "Adobe IMS response was not valid JSON") from exc
        if not token:
            raise AdobeAuthError(response.status_code, "Adobe IMS response did not include an access token")
        self._token = str(token)
        return self._token

    def auth_check(self) -> dict[str, Any]:
        try:
            self._get_token()
            return {"auth_status": "pass", "status_code": 200, "message": "IMS auth succeeded"}
        except AdobeAuthError as exc:
            return {
                "auth_status": "fail",
                "status_code": exc.status_code,
                "message": exc.safe_message,
            }

    def call(
        self,
        method: str,
        url: str,
        params: dict[str, Any] | None = None,
        headers: dict[str, Any] | None = None,
        body: Any | None = None,
    ) -> ApiResult:
        record_params = params or {}
        record_body = body
        request_params = _resolve_runtime_placeholders(record_params, self.settings)
        request_body = _resolve_runtime_placeholders(record_body, self.settings)
        parsed = urlparse(url)
        path = parsed.path if parsed.scheme else url
        started = time.perf_counter()
        request = ApiRequest(method=method.upper(), path=path, params=record_params, body=record_body)
        validation = self.catalog.validate(request)
        if not validation.valid:
            return ApiResult(
                method=method.upper(),
                url=f"{self.settings.adobe_base_url}{path}",
                params=record_params,
                body=record_body,
                status_code=400,
                result_preview=[],
                total=0,
                message=validation.error,
                endpoint_path=path,
                latency_seconds=time.perf_counter() - started,
                error_category="api_whitelist_rejection",
            )
        try:
            token = self._get_token()
        except AdobeAuthError as exc:
            return ApiResult(
                method=method.upper(),
                url=f"{self.settings.adobe_base_url}{path}",
                params=record_params,
                body=record_body,
                status_code=exc.status_code or 401,
                result_preview=[],
                total=0,
                message=exc.safe_message,
                endpoint_path=path,
                latency_seconds=time.perf_counter() - started,
                error_category="auth_or_permission",
            )
        request_headers = {
            "Authorization": f"Bearer {token}",
            "x-api-key": self.settings.adobe_client_id,
            "x-gw-ims-org-id": self.settings.adobe_ims_org,
            "x-sandbox-name": self.settings.adobe_sandbox,
            "Content-Type": "application/json",
        }
        schema_accept = _schema_accept_header(path)
        if schema_accept:
            request_headers["Accept"] = schema_accept
        request_headers.update(sanitize_headers(headers))
        base_url = f"{parsed.scheme}://{parsed.netloc}" if parsed.scheme else _base_url_for_path(self.settings, path)
        full_url = f"{base_url}{path}"
        try:
            response = requests.request(
                method.upper(),
                full_url,
                params=request_params,
                json=request_body,
                headers=request_headers,
                timeout=30,
            )
            if response.status_code in {429, 500, 502, 503, 504}:
                response = requests.request(
                    method.upper(),
                    full_url,
                    params=request_params,
                    json=request_body,
                    headers=request_headers,
                    timeout=30,
                )
            try:
                payload = response.json() if response.content else {}
            except ValueError:
                payload = {"text": safe_response_summary(response.text, self.settings)}
            preview = payload.get("items", payload.get("results", payload)) if isinstance(payload, dict) else payload
            if isinstance(preview, list):
                preview = preview[:10]
            preview = redact_payload(preview, self.settings)
            message = None
            if response.status_code >= 400:
                message = safe_response_summary(response.text, self.settings)
            return ApiResult(
                method=method.upper(),
                url=full_url,
                params=record_params,
                body=record_body,
                status_code=response.status_code,
                result_preview=preview,
                total=payload.get("total", payload.get("totalCount")) if isinstance(payload, dict) else None,
                message=message,
                endpoint_path=path,
                latency_seconds=time.perf_counter() - started,
                error_category=_error_category(response.status_code),
            )
        except Exception as exc:
            return ApiResult(
                method=method.upper(),
                url=full_url,
                params=record_params,
                body=record_body,
                status_code=500,
                result_preview=[],
                total=0,
                message=redact_error(str(exc), self.settings),
                endpoint_path=path,
                latency_seconds=time.perf_counter() - started,
                error_category="code_or_network",
            )
