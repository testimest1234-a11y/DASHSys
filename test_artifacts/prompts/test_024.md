You are a DASHSys local-first agent.

User query:
Is the audience 'Person: Birthday within 7 days' referenced in more than one journey simultaneously?

Selected metadata:
{
  "query": "Is the audience 'Person: Birthday within 7 days' referenced in more than one journey simultaneously?",
  "selected_intent": "audience_multi_journey_check",
  "confidence": 0.95,
  "entities": [
    {
      "raw_text": "Person: Birthday within 7 days",
      "matched_table": "dim_campaign",
      "matched_column": "NAME",
      "matched_value": "Birthday Message",
      "score": 85.5,
      "match_type": "fuzzy"
    }
  ],
  "relevant_schema": {
    "tables": [],
    "columns": {}
  },
  "join_paths": [],
  "candidate_api_endpoints": [],
  "selected_plan": {
    "id": "audience_multi_journey_check",
    "intent": "audience_multi_journey_check",
    "requires_sql": true,
    "requires_api": false,
    "sql_template_id": "audience_multi_journey_check",
    "api_template_ids": [],
    "required_entities": [
      "audience"
    ],
    "description": "audience multi journey check"
  },
  "router_evidence": [
    "audience",
    "multi journey"
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