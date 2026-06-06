from __future__ import annotations

from dashsys_agent.sql.templates import render_sql


def render_plan_sql(template_id: str | None, query: str) -> str | None:
    if not template_id:
        return None
    return render_sql(template_id, query)
