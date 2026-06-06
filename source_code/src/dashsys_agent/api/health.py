from __future__ import annotations

from typing import Any

from dashsys_agent.api.catalog import ApiCatalog
from dashsys_agent.api.real_client import RealAdobeApiClient
from dashsys_agent.api.sanitize import redact_error, redact_payload
from dashsys_agent.config import Settings


def real_api_health_check(settings: Settings) -> dict[str, Any]:
    report: dict[str, Any] = {
        "api_mode": settings.api_mode,
        "network_allowed": settings.allow_network,
        "sandbox": settings.adobe_sandbox,
        "sandbox_header": settings.adobe_sandbox,
        "adobe_credentials": "present",
        "tested_endpoint_path": "/ajo/journey",
        "auth": {"auth_status": "not_run", "status_code": None, "message": ""},
        "endpoint": {
            "status": "not_run",
            "http_status": None,
            "sanitized_response_preview": [],
            "error_category": None,
            "latency_seconds": None,
        },
    }
    if settings.api_mode != "real":
        report["auth"] = {
            "auth_status": "fail",
            "status_code": None,
            "message": "API_MODE is not real",
        }
        return report
    if not settings.allow_network:
        report["auth"] = {
            "auth_status": "fail",
            "status_code": None,
            "message": "ALLOW_NETWORK is false",
        }
        return report
    try:
        client = RealAdobeApiClient(settings, ApiCatalog.load())
    except ValueError as exc:
        report["auth"] = {"auth_status": "fail", "status_code": None, "message": redact_error(str(exc), settings)}
        report["adobe_credentials"] = "missing"
        return report
    report["auth"] = client.auth_check()
    if report["auth"]["auth_status"] != "pass":
        return report
    result = client.call("GET", "/ajo/journey", {"pageSize": "1"})
    report["endpoint"] = {
        "status": "pass" if result.status_code < 400 else "fail",
        "http_status": result.status_code,
        "sanitized_response_preview": redact_payload(result.result_preview, settings),
        "error_category": result.error_category,
        "latency_seconds": result.latency_seconds,
        "message": result.message,
    }
    return redact_payload(report, settings)
