You are a DASHSys local-first agent.

User query:
Show the details of batch 01KP6MNQ3X71RP6MNH6FHWGHVE.

Selected metadata:
{
  "query": "Show the details of batch 01KP6MNQ3X71RP6MNH6FHWGHVE.",
  "selected_intent": "batch_details",
  "confidence": 0.95,
  "entities": [
    {
      "raw_text": "01KP6MNQ3X71RP6MNH6FHWGHVE",
      "matched_table": "dim_collection",
      "matched_column": "TTLVALUE",
      "matched_value": "P13M",
      "score": 45.0,
      "match_type": "fuzzy"
    }
  ],
  "relevant_schema": {
    "tables": [],
    "columns": {}
  },
  "join_paths": [],
  "candidate_api_endpoints": [
    "GET /data/foundation/catalog/batches/01KP6MNQ3X71RP6MNH6FHWGHVE"
  ],
  "selected_plan": {
    "id": "batch_details",
    "intent": "batch_details",
    "requires_sql": false,
    "requires_api": true,
    "sql_template_id": null,
    "api_template_ids": [
      "GET /data/foundation/catalog/batches/01KP6MNQ3X71RP6MNH6FHWGHVE"
    ],
    "required_entities": [
      "batch"
    ],
    "description": "batch details"
  },
  "router_evidence": [
    "batch detail"
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