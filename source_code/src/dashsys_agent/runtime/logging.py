from __future__ import annotations

from datetime import datetime
from typing import Any

from dashsys_agent.api.sanitize import redact_payload
from dashsys_agent.config import Settings
from dashsys_agent.utils import has_secret


def append_runtime_log(settings: Settings, event: str, payload: dict[str, Any]) -> None:
    log_dir = settings.repo_root / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    record = redact_payload(
        {"timestamp": datetime.now().isoformat(timespec="seconds"), "event": event, **payload},
        settings,
    )
    text = str(record)
    if has_secret(text):
        record = {"timestamp": record["timestamp"], "event": event, "warning": "record redacted"}
    path = log_dir / "runtime.jsonl"
    with path.open("a", encoding="utf-8") as handle:
        handle.write(write_json_to_string(record) + "\n")


def write_json_to_string(payload: dict[str, Any]) -> str:
    import json

    from dashsys_agent.utils import to_jsonable

    return json.dumps(to_jsonable(payload), sort_keys=True, ensure_ascii=False)
