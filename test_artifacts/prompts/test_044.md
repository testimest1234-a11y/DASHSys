You are a DASHSys local-first agent.

User query:
Show all segment jobs with status 'CANCELLED'.

Selected metadata:
{
  "query": "Show all segment jobs with status 'CANCELLED'.",
  "selected_intent": "segment_jobs_by_status",
  "confidence": 0.95,
  "entities": [
    {
      "raw_text": "CANCELLED",
      "matched_table": "dim_blueprint",
      "matched_column": "CLASS",
      "matched_value": "CLASS",
      "score": 51.42857142857142,
      "match_type": "fuzzy"
    }
  ],
  "relevant_schema": {
    "tables": [],
    "columns": {}
  },
  "join_paths": [],
  "candidate_api_endpoints": [
    "GET /data/core/ups/segment/jobs"
  ],
  "selected_plan": {
    "id": "segment_jobs_by_status",
    "intent": "segment_jobs_by_status",
    "requires_sql": false,
    "requires_api": true,
    "sql_template_id": null,
    "api_template_ids": [
      "GET /data/core/ups/segment/jobs"
    ],
    "required_entities": [],
    "description": "segment jobs by status"
  },
  "router_evidence": [
    "segment jobs",
    "status"
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