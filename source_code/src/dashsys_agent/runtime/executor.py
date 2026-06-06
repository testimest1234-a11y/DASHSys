from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from dashsys_agent.api.edge_cases import (
    classify_entity_state_edge_case,
    supporting_catalog_request_for_api_failure,
)
from dashsys_agent.api.mock_client import MockApiClient
from dashsys_agent.api.real_client import RealAdobeApiClient
from dashsys_agent.api.request_adapter import adapt_request_for_real_api
from dashsys_agent.api.sanitize import redact_payload
from dashsys_agent.config import Settings
from dashsys_agent.db.duckdb_client import DuckDbClient
from dashsys_agent.db.join_graph import build_join_graph
from dashsys_agent.db.schema_catalog import build_schema_catalog
from dashsys_agent.llm.lmstudio_client import LmStudioClient
from dashsys_agent.planning.deterministic_planner import plan_query
from dashsys_agent.runtime.answer_builder import build_answer
from dashsys_agent.runtime.artifact_writer import ArtifactWriter
from dashsys_agent.runtime.evidence import EvidenceBundle
from dashsys_agent.runtime.logging import append_runtime_log
from dashsys_agent.runtime.metadata_builder import add_schema_context
from dashsys_agent.runtime.trajectory import validate_trajectory
from dashsys_agent.sql.render import render_plan_sql
from dashsys_agent.sql.validate import execute_sql
from dashsys_agent.utils import read_json, write_json


@dataclass
class RunMetrics:
    tool_calls: int = 0
    llm_available: bool = False
    llm_model: str | None = None
    local_llm_calls: int = 0
    llm_failures: int = 0
    llm_latency_seconds: list[float] = field(default_factory=list)
    llm_thinking_stripped_count: int = 0
    sql_success: bool = True
    api_whitelist_rejections: int = 0
    mock_fixture_hits: int = 0
    mock_fixture_misses: int = 0
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


@dataclass
class RunResult:
    query: str
    metadata: dict[str, Any]
    trajectory: dict[str, Any]
    answer: str
    metrics: RunMetrics
    raw_trajectory: dict[str, Any] | None = None


def load_or_build_catalog(db: DuckDbClient, settings: Settings) -> tuple[dict[str, Any], dict[str, Any]]:
    if settings.schema_catalog_path.exists() and settings.join_graph_path.exists():
        catalog = redact_payload(read_json(settings.schema_catalog_path), settings)
        join_graph = redact_payload(read_json(settings.join_graph_path), settings)
        write_json(settings.schema_catalog_path, catalog)
        write_json(settings.join_graph_path, join_graph)
        return catalog, join_graph
    catalog = build_schema_catalog(db.con, db.tables)
    join_graph = build_join_graph(catalog)
    catalog = redact_payload(catalog, settings)
    join_graph = redact_payload(join_graph, settings)
    write_json(settings.schema_catalog_path, catalog)
    write_json(settings.join_graph_path, join_graph)
    return catalog, join_graph


def make_api_client(settings: Settings) -> MockApiClient | RealAdobeApiClient:
    if settings.api_mode == "mock":
        return MockApiClient(settings)
    return RealAdobeApiClient(settings)


def run_query(
    query: str,
    settings: Settings,
    db: DuckDbClient | None = None,
    api_client: MockApiClient | RealAdobeApiClient | None = None,
    sample_id: str | None = None,
    write_artifacts: bool = True,
) -> RunResult:
    owns_db = db is None
    db = db or DuckDbClient.connect(settings)
    api_client = api_client or make_api_client(settings)
    metrics = RunMetrics()
    try:
        llm_client = LmStudioClient(settings)
        llm_status = llm_client.health_check()
        metrics.llm_available = llm_status.available
        metrics.llm_model = llm_status.model
        metrics.llm_latency_seconds = list(llm_client.metrics.llm_latency_seconds)
        metrics.warnings.extend(llm_client.metrics.warnings)
        append_runtime_log(
            settings,
            "llm_health_check",
            {
                "llm_status_text": llm_status.status_text,
                "llm_model_text": llm_status.model_text,
                "llm_available": llm_status.available,
                "llm_model": llm_status.model,
                "reason": llm_status.reason,
                "latency_seconds": llm_status.latency_seconds,
                "mode": "deterministic" if not llm_status.available else "deterministic_first",
            },
        )
        catalog, join_graph = load_or_build_catalog(db, settings)
        plan = plan_query(query, catalog)
        metadata = add_schema_context(plan.metadata(query), catalog, join_graph)
        metadata["llm"] = {
            "llm_available": metrics.llm_available,
            "llm_model": metrics.llm_model,
            "local_llm_calls": 0,
            "llm_failures": 0,
            "llm_thinking_stripped_count": 0,
            "warnings": list(metrics.warnings),
        }
        trace: list[dict[str, Any]] = []
        raw_trace: list[dict[str, Any]] = []
        evidence = EvidenceBundle(warnings=list(plan.warnings or []))
        step = 1

        if plan.selected_plan and plan.selected_plan.sql_template_id:
            sql = render_plan_sql(plan.selected_plan.sql_template_id, query)
            if sql:
                validation, rows = execute_sql(db.con, sql, settings.eval_max_rows)
                metrics.tool_calls += 1
                metrics.sql_success = validation.valid
                if validation.valid:
                    safe_rows = redact_payload(rows, settings)
                    evidence.sql_rows.extend(safe_rows)
                    raw_step = {
                        "step": step,
                        "action": "sql_query",
                        "sql": validation.sql,
                        "results": rows,
                        "status": "success",
                    }
                    safe_step = {
                        "step": step,
                        "action": "sql_query",
                        "sql": validation.sql,
                        "results": safe_rows,
                        "status": "success",
                    }
                    raw_trace.append(raw_step)
                    trace.append(safe_step)
                else:
                    evidence.errors.append(validation.error or "SQL validation failed")
                    raw_step = {
                        "step": step,
                        "action": "sql_query",
                        "sql": validation.sql,
                        "results": [],
                        "status": "error",
                    }
                    raw_trace.append(raw_step)
                    trace.append(raw_step)
                step += 1

        if plan.selected_plan:
            for request in plan.selected_plan.api_requests:
                if settings.api_mode != "mock":
                    request = adapt_request_for_real_api(request, query, evidence.sql_rows, evidence.api_records)
                result = api_client.call(request.method, request.path, request.params, body=request.body)
                metrics.tool_calls += 1
                raw_record = result.to_record()
                record = redact_payload(raw_record, settings)
                supporting_records: list[tuple[dict[str, Any], dict[str, Any]]] = []
                if settings.api_mode != "mock" and result.status_code >= 400:
                    support_request = supporting_catalog_request_for_api_failure(record)
                    if support_request:
                        support_result = api_client.call(
                            support_request.method,
                            support_request.path,
                            support_request.params,
                            body=support_request.body,
                        )
                        metrics.tool_calls += 1
                        support_raw_record = support_result.to_record()
                        support_record = redact_payload(support_raw_record, settings)
                        edge_case = classify_entity_state_edge_case(record, support_record)
                        if edge_case:
                            record["edge_case_category"] = edge_case["category"]
                            record["edge_case_handled"] = True
                            record["edge_case_evidence"] = edge_case
                            raw_record["edge_case_category"] = edge_case["category"]
                            raw_record["edge_case_handled"] = True
                            raw_record["edge_case_evidence"] = edge_case
                            support_record["edge_case_supporting_evidence"] = True
                            support_raw_record["edge_case_supporting_evidence"] = True
                            evidence.warnings.append(edge_case["category"])
                        supporting_records.append((support_raw_record, support_record))
                evidence.api_records.append(record)
                raw_trace.append({"step": step, "action": "api_call", "api_call": raw_record})
                trace.append({"step": step, "action": "api_call", "api_call": record})
                append_runtime_log(
                    settings,
                    "api_call",
                    {
                        "query_id": sample_id,
                        "api_mode": settings.api_mode,
                        "endpoint_path": result.endpoint_path or request.path,
                        "status_code": result.status_code,
                        "latency_seconds": result.latency_seconds,
                        "error_category": result.error_category,
                        "edge_case_category": record.get("edge_case_category"),
                        "sanitized_error": result.message if result.status_code >= 400 else None,
                        "llm_available": metrics.llm_available,
                        "llm_model": metrics.llm_model,
                        "local_llm_calls": metrics.local_llm_calls,
                        "llm_failures": metrics.llm_failures,
                    },
                )
                step += 1
                for support_raw_record, support_record in supporting_records:
                    evidence.api_records.append(support_record)
                    raw_trace.append({"step": step, "action": "api_call", "api_call": support_raw_record})
                    trace.append({"step": step, "action": "api_call", "api_call": support_record})
                    append_runtime_log(
                        settings,
                        "api_call",
                        {
                            "query_id": sample_id,
                            "api_mode": settings.api_mode,
                            "endpoint_path": support_record.get("endpoint_path"),
                            "status_code": support_record.get("status_code"),
                            "latency_seconds": support_record.get("latency_seconds"),
                            "error_category": support_record.get("error_category"),
                            "edge_case_supporting_evidence": support_record.get("edge_case_supporting_evidence"),
                            "sanitized_error": support_record.get("message")
                            if int(support_record.get("status_code", 0)) >= 400
                            else None,
                            "llm_available": metrics.llm_available,
                            "llm_model": metrics.llm_model,
                            "local_llm_calls": metrics.local_llm_calls,
                            "llm_failures": metrics.llm_failures,
                        },
                    )
                    step += 1

        metrics.local_llm_calls += plan.local_llm_calls
        metrics.local_llm_calls += llm_client.metrics.local_llm_calls
        metrics.llm_failures += llm_client.metrics.llm_failures
        metrics.llm_thinking_stripped_count += llm_client.metrics.llm_thinking_stripped_count
        metrics.llm_latency_seconds = list(llm_client.metrics.llm_latency_seconds)
        metrics.warnings.extend(llm_client.metrics.warnings)
        metadata["llm"]["local_llm_calls"] = metrics.local_llm_calls
        metadata["llm"]["llm_failures"] = metrics.llm_failures
        metadata["llm"]["llm_thinking_stripped_count"] = metrics.llm_thinking_stripped_count
        metadata["llm"]["warnings"] = list(dict.fromkeys(metrics.warnings))
        if isinstance(api_client, MockApiClient):
            metrics.api_whitelist_rejections = api_client.whitelist_rejections
            metrics.mock_fixture_hits = api_client.fixture_hits
            metrics.mock_fixture_misses = api_client.fixture_misses
        answer = str(redact_payload(build_answer(query, plan.intent_result.intent, evidence), settings))
        trajectory = redact_payload({"query": query, "trace": trace, "answer": answer}, settings)
        raw_trajectory = {"query": query, "trace": raw_trace, "answer": answer}
        validate_trajectory(trajectory)
        if write_artifacts:
            ArtifactWriter(settings).write(query, metadata, trajectory, answer, sample_id)
        return RunResult(
            query=query,
            metadata=metadata,
            trajectory=trajectory,
            answer=answer,
            metrics=metrics,
            raw_trajectory=raw_trajectory,
        )
    finally:
        if owns_db:
            db.close()
