from __future__ import annotations

from typing import Any


def _norm(name: str) -> str:
    return name.lower().replace("_", "")


def _dim_keys(catalog: dict[str, Any]) -> dict[str, set[str]]:
    keys: dict[str, set[str]] = {}
    for table, info in catalog.get("tables", {}).items():
        if not table.startswith("dim_"):
            continue
        keys[table] = {_norm(col) for col in info.get("columns", {})}
    return keys


def build_join_graph(catalog: dict[str, Any]) -> dict[str, Any]:
    dim_keys = _dim_keys(catalog)
    joins: list[dict[str, Any]] = []
    for bridge, info in catalog.get("tables", {}).items():
        if not (bridge.startswith("hkg_br_") or bridge.startswith("br_")):
            continue
        bridge_cols = {_norm(col): col for col in info.get("columns", {})}
        matched: list[tuple[str, str, str]] = []
        for dim_table, cols in dim_keys.items():
            common = sorted(set(bridge_cols).intersection(cols))
            if common:
                matched.append((dim_table, common[0], bridge_cols[common[0]]))
        for idx, left in enumerate(matched):
            for right in matched[idx + 1 :]:
                joins.append(
                    {
                        "left_table": left[0],
                        "left_key": left[1],
                        "bridge_table": bridge,
                        "bridge_left_key": left[2],
                        "right_table": right[0],
                        "right_key": right[1],
                        "bridge_right_key": right[2],
                        "confidence": 1.0,
                    }
                )
    return {"joins": joins}
