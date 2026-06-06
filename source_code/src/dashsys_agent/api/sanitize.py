from __future__ import annotations

import re
from typing import Any

from dashsys_agent.config import Settings

SENSITIVE_HEADER_NAMES = {"authorization", "x-api-key", "x-gw-ims-org-id", "cookie"}
SENSITIVE_FIELD_NAMES = {
    "authorization",
    "x-api-key",
    "x-gw-ims-org-id",
    "cookie",
    "access_token",
    "refresh_token",
    "client_secret",
    "adobe_client_secret",
}
SENSITIVE_FIELD_SUBSTRINGS = {
    "authorization",
    "access_token",
    "accesstoken",
    "refresh_token",
    "refreshtoken",
    "client_secret",
    "clientsecret",
    "request_id",
    "requestid",
    "x-api-key",
    "apikey",
    "x-gw-ims-org-id",
}


def sanitize_headers(headers: dict[str, Any] | None) -> dict[str, Any]:
    if not headers:
        return {}
    clean: dict[str, Any] = {}
    for key, value in headers.items():
        if key.lower() in SENSITIVE_HEADER_NAMES:
            continue
        clean[key] = value
    return clean


def redact_text(message: str, settings: Settings | None = None) -> str:
    if settings:
        for value in (
            settings.adobe_client_id,
            settings.adobe_client_secret,
            settings.adobe_ims_org,
        ):
            if value:
                message = message.replace(value, "[REDACTED]")
    message = re.sub(r"Bearer\s+[A-Za-z0-9._~+/=-]+", "Bearer [REDACTED]", message, flags=re.IGNORECASE)
    message = re.sub(r"eyJ[A-Za-z0-9_-]{20,}(?:\.[A-Za-z0-9_-]+){0,2}", "[REDACTED_TOKEN]", message)
    message = re.sub(r"access_token['\"]?\s*[:=]\s*['\"]?[^,'\"\s}]+", "access_token=[REDACTED]", message, flags=re.IGNORECASE)
    message = re.sub(r"\b[A-Fa-f0-9]{20,}@AdobeOrg\b", "[REDACTED_IMS_ORG]", message)
    for token in (
        "Authorization",
        "ADOBE_CLIENT_SECRET",
        "client_secret",
        "access_token",
        "x-api-key",
        "x-gw-ims-org-id",
    ):
        message = re.sub(re.escape(token), "[REDACTED]", message, flags=re.IGNORECASE)
    return message


def redact_error(message: str, settings: Settings | None = None) -> str:
    return redact_text(message, settings)


def _is_sensitive_field_name(key: str) -> bool:
    normalized = key.lower().replace("-", "_")
    compact = normalized.replace("_", "")
    return (
        normalized in SENSITIVE_FIELD_NAMES
        or any(part in normalized for part in SENSITIVE_FIELD_SUBSTRINGS)
        or any(part in compact for part in SENSITIVE_FIELD_SUBSTRINGS)
    )


def redact_payload(payload: Any, settings: Settings | None = None) -> Any:
    if isinstance(payload, str):
        return redact_text(payload, settings)
    if isinstance(payload, dict):
        clean: dict[str, Any] = {}
        for key, value in payload.items():
            key_text = str(key)
            if _is_sensitive_field_name(key_text):
                continue
            clean[key_text] = redact_payload(value, settings)
        return clean
    if isinstance(payload, list):
        return [redact_payload(item, settings) for item in payload]
    if isinstance(payload, tuple):
        return tuple(redact_payload(item, settings) for item in payload)
    return payload


def safe_response_summary(text: str, settings: Settings | None = None, limit: int = 500) -> str:
    return redact_error(text[:limit], settings)
