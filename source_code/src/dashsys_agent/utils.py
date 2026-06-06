from __future__ import annotations

import datetime as dt
import decimal
import json
import re
from pathlib import Path
from typing import Any

SECRET_PATTERNS = (
    re.compile(r"authorization", re.IGNORECASE),
    re.compile(r"bearer\s+[A-Za-z0-9._-]+", re.IGNORECASE),
    re.compile(r"adobe_client_secret", re.IGNORECASE),
    re.compile(r"access_token", re.IGNORECASE),
    re.compile(r"client_secret", re.IGNORECASE),
    re.compile(r"x-api-key", re.IGNORECASE),
    re.compile(r"x-gw-ims-org-id", re.IGNORECASE),
    re.compile(r"\b[A-Fa-f0-9]{20,}@AdobeOrg\b"),
    re.compile(r"eyJ[A-Za-z0-9_-]{20,}", re.IGNORECASE),
)


def normalize_bool(value: str | bool | None, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def to_jsonable(value: Any) -> Any:
    if isinstance(value, str):
        return value.replace("\u2014", ",")
    if isinstance(value, (dt.datetime, dt.date, dt.time)):
        return value.isoformat()
    if isinstance(value, decimal.Decimal):
        return float(value)
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(k): to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [to_jsonable(v) for v in value]
    return value


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(to_jsonable(payload), indent=2, ensure_ascii=False), encoding="utf-8")


def read_json(path: Path) -> Any:
    return to_jsonable(json.loads(path.read_text(encoding="utf-8")))


def stable_slug(text: str, max_len: int = 80) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", text.strip().lower()).strip("-")
    return slug[:max_len] or "query"


def has_secret(text: str) -> bool:
    return any(pattern.search(text) for pattern in SECRET_PATTERNS)


def normalize_text(value: str) -> str:
    cleaned = value.lower().strip()
    cleaned = cleaned.replace("\u2018", "'").replace("\u2019", "'").replace("\u201c", '"').replace("\u201d", '"')
    cleaned = cleaned.replace("-", " ").replace("_", " ")
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned


def normalize_row(row: dict[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    for key, value in row.items():
        key_norm = str(key).lower()
        if isinstance(value, str):
            normalized[key_norm] = re.sub(r"\s+", " ", value.strip())
        else:
            normalized[key_norm] = to_jsonable(value)
    return normalized


def rows_equal(left: list[dict[str, Any]], right: list[dict[str, Any]]) -> bool:
    def freeze(rows: list[dict[str, Any]]) -> list[str]:
        return sorted(json.dumps(normalize_row(row), sort_keys=True, default=str) for row in rows)

    return freeze(left) == freeze(right)
