from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass
class ApiResult:
    method: str
    url: str
    params: dict[str, Any]
    status_code: int
    result_preview: Any
    total: int | None = None
    body: Any | None = None
    mock: bool = False
    mock_fixture_miss: bool = False
    message: str | None = None
    endpoint_path: str | None = None
    latency_seconds: float | None = None
    error_category: str | None = None

    def to_record(self) -> dict[str, Any]:
        record: dict[str, Any] = {
            "method": self.method,
            "url": self.url,
            "params": self.params,
            "status_code": self.status_code,
            "result_preview": self.result_preview,
            "mock": self.mock,
        }
        if self.body is not None:
            record["body"] = self.body
        if self.total is not None:
            record["total"] = self.total
        if self.mock_fixture_miss:
            record["mock_fixture_miss"] = True
        if self.message:
            record["message"] = self.message
        if self.endpoint_path:
            record["endpoint_path"] = self.endpoint_path
        if self.latency_seconds is not None:
            record["latency_seconds"] = self.latency_seconds
        if self.error_category:
            record["error_category"] = self.error_category
        return record


class ApiClient(Protocol):
    def call(
        self,
        method: str,
        url: str,
        params: dict[str, Any] | None = None,
        headers: dict[str, Any] | None = None,
        body: Any | None = None,
    ) -> ApiResult:
        ...
