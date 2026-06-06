from __future__ import annotations

import json
import time
from dataclasses import replace
from typing import Any, ClassVar

import requests

from dashsys_agent.config import Settings
from dashsys_agent.llm.json_client import extract_final_json_object
from dashsys_agent.llm.metrics import LlmMetrics, LlmStatus


class LmStudioClient:
    _global_status: ClassVar[LlmStatus | None] = None

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._status: LlmStatus | None = None
        self.metrics = LlmMetrics()

    def health_check(self, force: bool = False) -> LlmStatus:
        if not self.settings.llm_enabled:
            status = LlmStatus(False, reason="LLM_ENABLED=false")
            self._status = status
            self.metrics.apply_status(status)
            return status
        if self._status is not None and not force:
            return self._status
        if LmStudioClient._global_status is not None and not force:
            self._status = replace(LmStudioClient._global_status, latency_seconds=None)
            self.metrics.apply_status(self._status)
            return self._status
        started = time.perf_counter()
        try:
            response = requests.get(
                f"{self.settings.llm_base_url}/models",
                timeout=min(10, self.settings.llm_timeout_seconds),
            )
            latency = time.perf_counter() - started
            response.raise_for_status()
            payload = response.json()
            data = payload.get("data", []) if isinstance(payload, dict) else []
            model = None
            if data and isinstance(data[0], dict):
                model = str(data[0].get("id") or data[0].get("model") or self.settings.llm_model)
            status = LlmStatus(True, model=model or self.settings.llm_model, latency_seconds=latency)
        except requests.RequestException:
            latency = time.perf_counter() - started
            status = LlmStatus(
                False,
                reason=f"Could not reach {self.settings.llm_base_url}",
                latency_seconds=latency,
            )
        except ValueError:
            latency = time.perf_counter() - started
            status = LlmStatus(
                False,
                reason=f"Invalid response from {self.settings.llm_base_url}/models",
                latency_seconds=latency,
            )
        self._status = status
        LmStudioClient._global_status = status
        self.metrics.apply_status(status)
        return status

    def available(self) -> bool:
        return self.health_check().available

    def select_plan(self, query: str, candidate_plans: list[dict[str, Any]]) -> str | None:
        if not self.health_check().available:
            return None
        allowed_ids = {plan["id"] for plan in candidate_plans}
        payload = {"query": query, "candidate_plans": candidate_plans}
        messages = [
            {"role": "system", "content": "Return JSON only. Choose one allowed selected_plan_id."},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ]
        started = time.perf_counter()
        self.metrics.local_llm_calls += 1
        try:
            response = requests.post(
                f"{self.settings.llm_base_url}/chat/completions",
                json={
                    "model": self._status.model if self._status and self._status.model else self.settings.llm_model,
                    "messages": messages,
                    "temperature": self.settings.llm_temperature,
                    "max_tokens": min(self.settings.llm_max_tokens, 512),
                },
                headers={"Authorization": f"Bearer {self.settings.llm_api_key}"},
                timeout=self.settings.llm_timeout_seconds,
            )
            response.raise_for_status()
            self.metrics.llm_latency_seconds.append(time.perf_counter() - started)
            content = response.json()["choices"][0]["message"]["content"]
            extraction = extract_final_json_object(content)
            if extraction.thinking_stripped:
                self.metrics.llm_thinking_stripped_count += 1
            parsed = extraction.payload
        except (requests.RequestException, KeyError, IndexError, TypeError, ValueError):
            self.metrics.llm_failures += 1
            self.metrics.warnings.append("Local LLM plan selection failed. Running deterministic mode only.")
            return None
        selected = parsed.get("selected_plan_id") if parsed else None
        if selected not in allowed_ids:
            self.metrics.llm_failures += 1
            self.metrics.warnings.append("Local LLM returned an invalid plan ID. Running deterministic mode only.")
            return None
        return str(selected) if selected in allowed_ids else None
