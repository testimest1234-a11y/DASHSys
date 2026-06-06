from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class LlmStatus:
    available: bool
    model: str | None = None
    reason: str | None = None
    latency_seconds: float | None = None

    @property
    def status_text(self) -> str:
        return "LLM status: available" if self.available else "LLM status: unavailable"

    @property
    def model_text(self) -> str:
        return f"LLM model: {self.model}" if self.model else "LLM model: unavailable"


@dataclass
class LlmMetrics:
    llm_available: bool = False
    llm_model: str | None = None
    local_llm_calls: int = 0
    llm_failures: int = 0
    llm_latency_seconds: list[float] = field(default_factory=list)
    llm_thinking_stripped_count: int = 0
    warnings: list[str] = field(default_factory=list)

    def apply_status(self, status: LlmStatus) -> None:
        self.llm_available = status.available
        self.llm_model = status.model
        if status.latency_seconds is not None:
            self.llm_latency_seconds.append(status.latency_seconds)
        if not status.available:
            reason = status.reason or "Could not reach local LM Studio endpoint"
            self.warnings.append(f"{reason}. Running deterministic mode only.")

    def to_dict(self) -> dict:
        return {
            "llm_available": self.llm_available,
            "llm_model": self.llm_model,
            "local_llm_calls": self.local_llm_calls,
            "llm_failures": self.llm_failures,
            "llm_latency_seconds": self.llm_latency_seconds,
            "llm_thinking_stripped_count": self.llm_thinking_stripped_count,
            "warnings": self.warnings,
        }
