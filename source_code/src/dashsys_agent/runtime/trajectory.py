from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from dashsys_agent.utils import has_secret


class ApiCallRecord(BaseModel):
    method: str
    url: str
    params: dict[str, Any] = Field(default_factory=dict)
    body: Any | None = None
    status_code: int
    result_preview: Any = Field(default_factory=list)
    total: int | None = None
    mock: bool | None = None
    mock_fixture_miss: bool | None = None
    message: str | None = None
    endpoint_path: str | None = None
    latency_seconds: float | None = None
    error_category: str | None = None

    @model_validator(mode="after")
    def no_secret_content(self) -> ApiCallRecord:
        text = self.model_dump_json()
        if has_secret(text):
            raise ValueError("API call record contains secret-like content")
        return self


class TraceStep(BaseModel):
    step: int
    action: Literal["sql_query", "api_call"]
    sql: str | None = None
    results: list[dict[str, Any]] | None = None
    status: str | None = None
    api_call: ApiCallRecord | None = None

    @model_validator(mode="after")
    def validate_shape(self) -> TraceStep:
        if self.action == "sql_query":
            if not self.sql or self.results is None or not self.status:
                raise ValueError("SQL step requires sql, results, and status")
        if self.action == "api_call" and self.api_call is None:
            raise ValueError("API step requires api_call")
        return self


class Trajectory(BaseModel):
    query: str
    trace: list[TraceStep]
    answer: str

    @model_validator(mode="after")
    def validate_steps_and_secrets(self) -> Trajectory:
        expected = list(range(1, len(self.trace) + 1))
        actual = [step.step for step in self.trace]
        if actual != expected:
            raise ValueError(f"Trace steps must be consecutive from 1: {actual}")
        if has_secret(self.model_dump_json()):
            raise ValueError("Trajectory contains secret-like content")
        return self


def validate_trajectory(payload: dict[str, Any]) -> Trajectory:
    if has_secret(json.dumps(payload, ensure_ascii=False, default=str)):
        raise ValueError("Trajectory contains secret-like content")
    return Trajectory.model_validate(payload)
