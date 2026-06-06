You are a DASHSys local-first agent.

User query:
For the audience 'Gender: Female', what is its profile count, is it batch or streaming, and how many audiences share the same rule definition?

Selected metadata:
{
  "query": "For the audience 'Gender: Female', what is its profile count, is it batch or streaming, and how many audiences share the same rule definition?",
  "selected_intent": "audience_profile_summary",
  "confidence": 0.95,
  "entities": [
    {
      "raw_text": "Gender: Female",
      "matched_table": "dim_segment",
      "matched_column": "NAME",
      "matched_value": "Gender: Female",
      "score": 100.0,
      "match_type": "exact"
    }
  ],
  "relevant_schema": {
    "tables": [],
    "columns": {}
  },
  "join_paths": [],
  "candidate_api_endpoints": [],
  "selected_plan": {
    "id": "audience_profile_summary",
    "intent": "audience_profile_summary",
    "requires_sql": true,
    "requires_api": false,
    "sql_template_id": "audience_profile_summary",
    "api_template_ids": [],
    "required_entities": [
      "audience"
    ],
    "description": "audience profile summary"
  },
  "router_evidence": [
    "audience",
    "profile count"
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