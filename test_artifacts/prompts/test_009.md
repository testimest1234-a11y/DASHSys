You are a DASHSys local-first agent.

User query:
List all datasets that use the schema 'hkg_adls_segment_profile_history'.

Selected metadata:
{
  "query": "List all datasets that use the schema 'hkg_adls_segment_profile_history'.",
  "selected_intent": "datasets_for_schema",
  "confidence": 0.92,
  "entities": [
    {
      "raw_text": "hkg_adls_segment_profile_history",
      "matched_table": "dim_collection",
      "matched_column": "NAME",
      "matched_value": "hkg_adls_segment_profile_history",
      "score": 100.0,
      "match_type": "exact"
    }
  ],
  "relevant_schema": {
    "tables": [
      "hkg_br_blueprint_collection",
      "dim_collection",
      "dim_blueprint"
    ],
    "columns": {
      "hkg_br_blueprint_collection": [
        "COLLECTIONID",
        "LABELSBLUEPRINT",
        "BLUEPRINTID",
        "LABELSCOLLECTION"
      ],
      "dim_collection": [
        "ISIDENTITYENABLED",
        "ROWCOUNT",
        "UPDATEDTIME",
        "STORAGESIZEINBYTES",
        "ISPROFILEENABLED",
        "NAME",
        "COLLECTIONID",
        "ISSYSTEM",
        "STORAGESIZEINMEGABYTES",
        "ISTTLSET",
        "CREATEDTIME",
        "UPDATEDBY",
        "TTLVALUE",
        "CREATEDBY",
        "CREATEDCLIENTID",
        "LABELSCOLLECTION"
      ],
      "dim_blueprint": [
        "BLUEPRINTTYPE",
        "EXTENDS",
        "UPDATEDCLIENTID",
        "LABELSBLUEPRINT",
        "UPDATEDTIME",
        "CLASS",
        "BLUEPRINTID",
        "IMMUTABLETAGS",
        "TENANT",
        "ISPROFILEENABLED",
        "NAME",
        "ISBEHAVIORTIMESERIESTYPE",
        "DESCRIPTION",
        "ETAG",
        "REQUIREDFIELDS",
        "ISBEHAVIORRECORDTYPE",
        "CREATEDTIME",
        "UPDATEDBY",
        "CREATEDBY",
        "CREATEDCLIENTID"
      ]
    }
  },
  "join_paths": [
    {
      "left_table": "dim_blueprint",
      "left_key": "blueprintid",
      "bridge_table": "hkg_br_blueprint_collection",
      "bridge_left_key": "BLUEPRINTID",
      "right_table": "dim_collection",
      "right_key": "collectionid",
      "bridge_right_key": "COLLECTIONID",
      "confidence": 1.0
    }
  ],
  "candidate_api_endpoints": [
    "GET /data/foundation/catalog/dataSets",
    "GET /data/foundation/schemaregistry/tenant/schemas/{schema_id}"
  ],
  "selected_plan": {
    "id": "datasets_for_schema",
    "intent": "datasets_for_schema",
    "requires_sql": true,
    "requires_api": true,
    "sql_template_id": "datasets_for_schema",
    "api_template_ids": [
      "GET /data/foundation/catalog/dataSets",
      "GET /data/foundation/schemaregistry/tenant/schemas/{schema_id}"
    ],
    "required_entities": [
      "schema"
    ],
    "description": "datasets for schema"
  },
  "router_evidence": [
    "datasets",
    "schema"
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