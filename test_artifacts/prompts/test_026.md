You are a DASHSys local-first agent.

User query:
List all audiences used by live journeys with 'streaming' in the journey name.

Selected metadata:
{
  "query": "List all audiences used by live journeys with 'streaming' in the journey name.",
  "selected_intent": "audiences_for_live_journey_keyword",
  "confidence": 0.95,
  "entities": [
    {
      "raw_text": "streaming",
      "matched_table": "dim_connector",
      "matched_column": "CATEGORY",
      "matched_value": "streaming",
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
    "id": "audiences_for_live_journey_keyword",
    "intent": "audiences_for_live_journey_keyword",
    "requires_sql": true,
    "requires_api": false,
    "sql_template_id": "audiences_for_live_journey_keyword",
    "api_template_ids": [],
    "required_entities": [
      "journey_keyword"
    ],
    "description": "audiences for live journey keyword"
  },
  "router_evidence": [
    "audience",
    "live journey"
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