from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from dashsys_agent.config import Settings
from dashsys_agent.utils import read_json


@dataclass(frozen=True)
class Sample:
    sample_id: str
    query: str
    trace: list[dict[str, Any]]
    answer: str
    gold_sql: str
    gold_api: list[str]


def load_samples(settings: Settings) -> list[Sample]:
    payload = read_json(settings.samples_path)
    samples = []
    for idx, row in enumerate(payload, start=1):
        samples.append(
            Sample(
                sample_id=f"sample-{idx:02d}",
                query=row.get("query", ""),
                trace=row.get("trace", []),
                answer=row.get("answer", ""),
                gold_sql=row.get("gold_sql") or "",
                gold_api=row.get("gold_api") or [],
            )
        )
    return samples
