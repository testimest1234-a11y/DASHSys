You are a DASHSys local-first agent.

User query:
Show all segment jobs with status 'PROCESSING'.

Selected metadata:
{
  "query": "Show all segment jobs with status 'PROCESSING'.",
  "selected_intent": "processing_segment_jobs",
  "confidence": 0.95,
  "entities": [
    {
      "raw_text": "PROCESSING",
      "matched_table": "dim_blueprint",
      "matched_column": "CLASS",
      "matched_value": "CLASS",
      "score": 54.0,
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
    "id": "processing_segment_jobs",
    "intent": "processing_segment_jobs",
    "requires_sql": false,
    "requires_api": true,
    "sql_template_id": null,
    "api_template_ids": [
      "GET /data/core/ups/segment/jobs"
    ],
    "required_entities": [],
    "description": "processing segment jobs"
  },
  "router_evidence": [
    "segment jobs",
    "processing"
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