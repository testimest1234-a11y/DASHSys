You are a DASHSys local-first agent.

User query:
Show me the details of the tag named 'test'.

Selected metadata:
{
  "query": "Show me the details of the tag named 'test'.",
  "selected_intent": "tag_details",
  "confidence": 0.95,
  "entities": [
    {
      "raw_text": "test",
      "matched_table": "dim_collection",
      "matched_column": "NAME",
      "matched_value": "BR_Namespace_Destination",
      "score": 67.5,
      "match_type": "fuzzy"
    }
  ],
  "relevant_schema": {
    "tables": [],
    "columns": {}
  },
  "join_paths": [],
  "candidate_api_endpoints": [
    "GET /unifiedtags/tags"
  ],
  "selected_plan": {
    "id": "tag_details",
    "intent": "tag_details",
    "requires_sql": false,
    "requires_api": true,
    "sql_template_id": null,
    "api_template_ids": [
      "GET /unifiedtags/tags"
    ],
    "required_entities": [
      "tag"
    ],
    "description": "tag details"
  },
  "router_evidence": [
    "tag detail"
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