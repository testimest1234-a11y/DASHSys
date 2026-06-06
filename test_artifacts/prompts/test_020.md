You are a DASHSys local-first agent.

User query:
Do I have audiences with the same logic but different names?

Selected metadata:
{
  "query": "Do I have audiences with the same logic but different names?",
  "selected_intent": "duplicate_audience_groups",
  "confidence": 0.95,
  "entities": [],
  "relevant_schema": {
    "tables": [],
    "columns": {}
  },
  "join_paths": [],
  "candidate_api_endpoints": [],
  "selected_plan": {
    "id": "duplicate_audience_groups",
    "intent": "duplicate_audience_groups",
    "requires_sql": true,
    "requires_api": false,
    "sql_template_id": "duplicate_audience_groups",
    "api_template_ids": [],
    "required_entities": [],
    "description": "duplicate audience groups"
  },
  "router_evidence": [
    "duplicate audience rules"
  ],
  "warnings": [],
  "llm": {
    "llm_available": false,
    "llm_model": null,
    "local_llm_calls": 0,
    "llm_failures": 0,
    "llm_thinking_stripped_count": 0,
    "warnings": [
      "Could not reach http://localhost:1234/v1. Running deterministic mode only."
    ]
  }
}

Allowed tools:
- execute_sql(sql)
- call_api(method, url, params, headers)

Rules:
- Use only provided schema.
- Use only provided API endpoints.
- Do not invent tables, columns, or API paths.
- Do not include secrets or auth headers.
- Output valid trajectory JSON.
- The final answer must be based only on tool results.