from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class JsonExtractionResult:
    payload: dict[str, Any] | None
    thinking_stripped: bool


def extract_json_object(text: str) -> dict[str, Any] | None:
    return extract_final_json_object(text).payload


def _json_candidates(text: str) -> list[str]:
    candidates: list[str] = []
    fenced = re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.DOTALL | re.IGNORECASE)
    candidates.extend(fenced)
    starts = [idx for idx, char in enumerate(text) if char == "{"]
    for start in starts:
        depth = 0
        in_string = False
        escape = False
        for idx in range(start, len(text)):
            char = text[idx]
            if in_string:
                if escape:
                    escape = False
                elif char == "\\":
                    escape = True
                elif char == '"':
                    in_string = False
                continue
            if char == '"':
                in_string = True
            elif char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    candidates.append(text[start : idx + 1])
                    break
    return candidates


def extract_final_json_object(text: str) -> JsonExtractionResult:
    stripped_source = text
    stripped_source = re.sub(r"<think>.*?</think>", "", stripped_source, flags=re.DOTALL | re.IGNORECASE)
    stripped_source = re.sub(r"<thinking>.*?</thinking>", "", stripped_source, flags=re.DOTALL | re.IGNORECASE)
    try:
        payload = json.loads(stripped_source)
        if isinstance(payload, dict):
            return JsonExtractionResult(payload, stripped_source.strip() != text.strip())
    except json.JSONDecodeError:
        pass
    for candidate in reversed(_json_candidates(stripped_source)):
        try:
            payload = json.loads(candidate)
            if isinstance(payload, dict):
                thinking_stripped = stripped_source.strip() != candidate.strip() or stripped_source.strip() != text.strip()
                return JsonExtractionResult(payload, thinking_stripped)
        except json.JSONDecodeError:
            continue
    return JsonExtractionResult(None, stripped_source.strip() != text.strip())
