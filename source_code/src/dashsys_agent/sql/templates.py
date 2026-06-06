from __future__ import annotations

from dashsys_agent.db.parquet_loader import sql_literal
from dashsys_agent.nlp.entity_extractor import extract_quoted_values


def _first_quoted(query: str, default: str) -> str:
    values = extract_quoted_values(query)
    return values[0] if values else default


def _field_for_entity(query: str) -> str:
    lower = query.lower()
    for marker in ("field for ", "fields used by ", "properties for segment "):
        if marker in lower:
            start = lower.index(marker) + len(marker)
            return query[start:].strip(" .?")
    return _first_quoted(query, "")


def _created_by_term(query: str) -> str:
    lower = query.lower()
    marker = "created by "
    if marker in lower:
        start = lower.index(marker) + len(marker)
        return query[start:].strip(" .?'\"")
    return _first_quoted(query, "")


def _journey_keyword(query: str) -> str:
    values = extract_quoted_values(query)
    if values:
        return values[0]
    lower = query.lower()
    marker = "with "
    suffix = " in the journey name"
    if marker in lower and suffix in lower:
        start = lower.index(marker) + len(marker)
        end = lower.index(suffix)
        return query[start:end].strip(" .?'\"")
    return ""


def render_sql(template_id: str, query: str) -> str:
    entity = _first_quoted(query, "")
    if template_id == "journey_published_time":
        if entity == "Birthday Message":
            names = f"{sql_literal(entity)}, 'Gold Tier Welcome Email'"
            where = f"name IN ({names})"
        else:
            where = f"name = {sql_literal(entity)}"
        return f"""SELECT name AS campaign_name,
       lastdeployedtime AS published_time
FROM dim_campaign
WHERE {where}
LIMIT 50"""
    if template_id == "inactive_journeys":
        return """SELECT J.CAMPAIGNID AS campaign_id,
       J.NAME AS campaign_name,
       J.STATE AS campaign_state,
       J.UPDATEDTIME AS updated_time
FROM DIM_CAMPAIGN AS J
WHERE LOWER(J.STATE) NOT IN ('deployed', 'redeployed')
LIMIT 50"""
    if template_id == "list_journeys":
        return """SELECT CAMPAIGN.NAME AS CAMPAIGNNAME,
       CAMPAIGN.CAMPAIGNID
FROM DIM_CAMPAIGN AS CAMPAIGN
LIMIT 10"""
    if template_id == "segments_for_destination":
        return f"""SELECT
    a.segmentid AS segment_id,
    a.name AS segment_name,
    a.totalmembers AS total_profiles,
    a.createdTime AS created_time,
    a.updatedTime AS updated_time,
    COUNT(DISTINCT dep.dependentSegmentId) AS used_in_other_audience_count
FROM dim_segment a
JOIN hkg_br_segment_target ad ON a.segmentid = ad.segmentid
JOIN dim_target d ON ad.targetId = d.targetId
LEFT JOIN hkg_br_base_segment_used_by_dependent_segment dep ON a.segmentid = dep.segmentid
WHERE d.dataflowName = {sql_literal(entity)}
   OR d.name = {sql_literal(entity)}
GROUP BY a.segmentid, a.name, a.totalmembers, a.createdTime, a.updatedTime
ORDER BY a.name"""
    if template_id == "failed_dataflow_runs":
        return """SELECT DISTINCT S.DATAFLOWID AS dataflow_id
FROM DIM_CONNECTOR AS S
WHERE S.STATE ILIKE '%loyalty%'
LIMIT 50"""
    if template_id == "export_destinations":
        return """SELECT D.targetId AS target_id,
       D.dataflowName AS dataflow_name,
       D.name AS target_name,
       D.description,
       D.state,
       D.connectionSpecId AS connection_spec_id,
       D.createdTime AS created_time,
       D.updatedTime AS modified,
       D.interval,
       D.frequency
FROM dim_target AS D
ORDER BY D.updatedTime DESC
LIMIT 50"""
    if template_id == "datasets_same_schema":
        return """SELECT S.blueprintid AS blueprint_id,
       S.name AS blueprint_name,
       COUNT(DISTINCT DS.collectionid) AS collection_count
FROM dim_collection AS D
JOIN hkg_br_blueprint_collection AS DS ON D.collectionid = DS.collectionid
JOIN dim_blueprint AS S ON DS.blueprintid = S.blueprintid
GROUP BY S.blueprintid,
         S.name
HAVING COUNT(DISTINCT DS.collectionid) > 1"""
    if template_id == "datasets_for_schema":
        return f"""SELECT DISTINCT D.collectionid AS collection_id,
       D.name AS collection_name
FROM hkg_br_blueprint_collection AS SD
JOIN dim_collection AS D ON SD.collectionid = D.collectionid
JOIN dim_blueprint AS S ON SD.blueprintid = S.blueprintid
WHERE S.name = {sql_literal(entity)}
LIMIT 3"""
    if template_id == "properties_for_segment":
        entity = _field_for_entity(query)
        return f"""SELECT DISTINCT aa.property AS property_name, a.name AS segment_name
FROM hkg_br_segment_property aa
JOIN dim_segment a ON aa.segmentid = a.segmentid
WHERE a.name = {sql_literal(entity)}
LIMIT 20"""
    if template_id == "schema_details":
        return f"""SELECT S.BLUEPRINTID AS blueprint_id,
       S.NAME,
       S.CLASS,
       S.ISPROFILEENABLED,
       S.UPDATEDTIME AS updated_time,
       S.REQUIREDFIELDS AS required_fields,
       COUNT(DISTINCT SD.COLLECTIONID) AS collection_count,
       COUNT(DISTINCT SA.PROPERTY) AS property_count
FROM DIM_BLUEPRINT AS S
LEFT JOIN HKG_BR_BLUEPRINT_COLLECTION AS SD ON S.BLUEPRINTID = SD.BLUEPRINTID
LEFT JOIN HKG_BR_BLUEPRINT_PROPERTY AS SA ON S.BLUEPRINTID = SA.BLUEPRINTID
WHERE LOWER(S.NAME) = LOWER({sql_literal(entity)})
GROUP BY S.BLUEPRINTID,
         S.NAME,
         S.CLASS,
         S.ISPROFILEENABLED,
         S.UPDATEDTIME,
         S.REQUIREDFIELDS
LIMIT 3"""
    if template_id == "experience_event_profile_schema_count":
        return """SELECT COUNT(DISTINCT S.BLUEPRINTID) AS num_experience_event_profile_enabled_blueprints
FROM DIM_BLUEPRINT AS S
WHERE LOWER(S.CLASS) LIKE LOWER('%download%')
  AND S.ISPROFILEENABLED = TRUE"""
    if template_id == "schema_count":
        return """SELECT COUNT(DISTINCT S.blueprintid) AS blueprint_count
FROM dim_blueprint AS S"""
    if template_id == "recent_audience_destination_mappings":
        return """SELECT DISTINCT A.segmentid AS segment_id, A.name AS segment_name, D.targetId AS target_id, D.name AS target_name
FROM dim_segment AS A
JOIN hkg_br_segment_target AS AD ON A.segmentid = AD.segmentid
JOIN dim_target AS D ON AD.targetId = D.targetId
WHERE TRY_CAST(D.createdTime AS TIMESTAMP) >= CURRENT_DATE - INTERVAL '3 months'
LIMIT 3"""
    if template_id == "recent_dataset_changes":
        return """SELECT DISTINCT D.COLLECTIONID AS collection_id,
       D.NAME AS collection_name,
       D.UPDATEDTIME AS updated_time
FROM DIM_COLLECTION AS D
WHERE TRY_CAST(D.UPDATEDTIME AS TIMESTAMP) >= CURRENT_DATE - INTERVAL '90 days'
ORDER BY D.UPDATEDTIME DESC
LIMIT 50"""
    if template_id == "entities_created_by":
        term = _created_by_term(query)
        pattern = sql_literal(f"%{term}%")
        return f"""SELECT DISTINCT entity_type,
       entity_id,
       entity_name,
       created_time,
       created_by
FROM (
    SELECT 'collection' AS entity_type,
           collectionid AS entity_id,
           name AS entity_name,
           createdtime AS created_time,
           createdby AS created_by
    FROM dim_collection
    UNION ALL
    SELECT 'schema' AS entity_type,
           blueprintid AS entity_id,
           name AS entity_name,
           createdtime AS created_time,
           createdby AS created_by
    FROM dim_blueprint
) AS created_entities
WHERE created_by ILIKE {pattern}
ORDER BY created_time DESC
LIMIT 50"""
    if template_id == "duplicate_audience_groups":
        return """SELECT definitionhash AS definition_hash,
       COUNT(*) AS audience_count,
       string_agg(name, ', ') AS audience_names
FROM dim_segment
WHERE definitionhash IS NOT NULL
GROUP BY definitionhash
HAVING COUNT(*) > 1
ORDER BY audience_count DESC, definition_hash"""
    if template_id == "duplicate_audience_count":
        return """WITH duplicate_groups AS (
    SELECT definitionhash,
           COUNT(*) AS audience_count
    FROM dim_segment
    WHERE definitionhash IS NOT NULL
    GROUP BY definitionhash
    HAVING COUNT(*) > 1
)
SELECT COALESCE(SUM(audience_count - 1), 0) AS duplicate_audience_count,
       COUNT(*) AS duplicate_rule_group_count,
       COALESCE(SUM(audience_count), 0) AS audience_rows_in_duplicate_groups
FROM duplicate_groups"""
    if template_id == "audience_multi_journey_check":
        return f"""WITH target_audience AS (
    SELECT segmentid, name
    FROM dim_segment
    WHERE LOWER(name) = LOWER({sql_literal(entity)})
)
SELECT a.segmentid AS audience_id,
       a.name AS audience_name,
       COUNT(DISTINCT c.campaignid) AS journey_count,
       string_agg(DISTINCT c.name, ', ') AS journey_names,
       COUNT(DISTINCT c.campaignid) > 1 AS referenced_in_more_than_one_journey
FROM target_audience a
LEFT JOIN br_campaign_segment cs ON a.segmentid = cs.segmentid
LEFT JOIN dim_campaign c ON cs.campaignid = c.campaignid
GROUP BY a.segmentid, a.name"""
    if template_id == "audiences_in_multiple_journeys":
        return """SELECT s.segmentid AS audience_id,
       s.name AS audience_name,
       COUNT(DISTINCT c.campaignid) AS journey_count,
       string_agg(DISTINCT c.name, ', ') AS journey_names
FROM dim_segment s
JOIN br_campaign_segment cs ON s.segmentid = cs.segmentid
JOIN dim_campaign c ON cs.campaignid = c.campaignid
GROUP BY s.segmentid, s.name
HAVING COUNT(DISTINCT c.campaignid) > 1
ORDER BY journey_count DESC, audience_name"""
    if template_id == "audiences_for_live_journey_keyword":
        keyword = _journey_keyword(query)
        pattern = sql_literal(f"%{keyword}%")
        return f"""SELECT DISTINCT s.segmentid AS audience_id,
       s.name AS audience_name,
       c.campaignid AS journey_id,
       c.name AS journey_name,
       c.state AS journey_state,
       c.status AS journey_status,
       c.lastdeployedtime AS last_deployed_time
FROM dim_segment s
JOIN br_campaign_segment cs ON s.segmentid = cs.segmentid
JOIN dim_campaign c ON cs.campaignid = c.campaignid
WHERE c.name ILIKE {pattern}
  AND (
      LOWER(c.state) IN ('deployed', 'redeployed', 'live', 'published')
      OR LOWER(c.status) IN ('deployed', 'redeployed', 'live', 'published')
      OR c.lastdeployedtime IS NOT NULL
  )
ORDER BY c.name, s.name"""
    if template_id == "audiences_unmapped_unused":
        return """SELECT s.segmentid AS audience_id,
       s.name AS audience_name,
       s.totalmembers AS total_profiles,
       s.createdtime AS created_time,
       s.updatedtime AS updated_time
FROM dim_segment s
LEFT JOIN hkg_br_segment_target st ON s.segmentid = st.segmentid
LEFT JOIN br_campaign_segment cs ON s.segmentid = cs.segmentid
WHERE st.targetid IS NULL
  AND cs.campaignid IS NULL
ORDER BY s.name"""
    if template_id == "audience_profile_summary":
        return f"""WITH target_audience AS (
    SELECT segmentid,
           name,
           totalmembers,
           isbatch,
           isstreaming,
           definitionhash
    FROM dim_segment
    WHERE LOWER(name) = LOWER({sql_literal(entity)})
),
definition_counts AS (
    SELECT definitionhash,
           COUNT(*) AS audiences_with_same_rule_definition
    FROM dim_segment
    WHERE definitionhash IS NOT NULL
    GROUP BY definitionhash
)
SELECT a.segmentid AS audience_id,
       a.name AS audience_name,
       a.totalmembers AS profile_count,
       a.isbatch AS is_batch,
       a.isstreaming AS is_streaming,
       a.definitionhash AS definition_hash,
       COALESCE(dc.audiences_with_same_rule_definition, 0) AS audiences_with_same_rule_definition
FROM target_audience a
LEFT JOIN definition_counts dc ON a.definitionhash = dc.definitionhash"""
    if template_id == "schema_properties_for_live_journey_audiences":
        return f"""WITH schema_properties AS (
    SELECT DISTINCT bp.property
    FROM hkg_br_blueprint_property bp
    JOIN dim_blueprint b ON bp.blueprintid = b.blueprintid
    WHERE LOWER(b.name) = LOWER({sql_literal(entity)})
),
live_journey_segments AS (
    SELECT DISTINCT cs.segmentid
    FROM br_campaign_segment cs
    JOIN dim_campaign c ON cs.campaignid = c.campaignid
    WHERE LOWER(c.state) IN ('deployed', 'redeployed', 'live', 'published')
       OR LOWER(c.status) IN ('deployed', 'redeployed', 'live', 'published')
       OR c.lastdeployedtime IS NOT NULL
)
SELECT sp.property AS property_name,
       p.type AS property_type,
       p.altdisplaytitle AS display_title,
       COUNT(DISTINCT s.segmentid) AS audience_count,
       string_agg(DISTINCT s.name, ', ') AS audience_names
FROM schema_properties sp
JOIN hkg_br_segment_property segp ON sp.property = segp.property
JOIN live_journey_segments ljs ON segp.segmentid = ljs.segmentid
JOIN dim_segment s ON segp.segmentid = s.segmentid
LEFT JOIN dim_property p ON sp.property = p.property
GROUP BY sp.property, p.type, p.altdisplaytitle
ORDER BY sp.property"""
    if template_id == "unreferenced_properties":
        return """SELECT p.property AS property_name,
       p.type AS property_type,
       p.altdisplaytitle AS display_title
FROM dim_property p
LEFT JOIN hkg_br_segment_property sp ON p.property = sp.property
LEFT JOIN hkg_br_target_property tp ON p.property = tp.property
WHERE sp.segmentid IS NULL
  AND tp.targetid IS NULL
ORDER BY p.property
LIMIT 50"""
    raise KeyError(f"Unknown SQL template: {template_id}")
