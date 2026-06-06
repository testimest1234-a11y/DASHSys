from __future__ import annotations

from dashsys_agent.utils import normalize_text


def normalize_query(query: str) -> str:
    return normalize_text(query)
