from __future__ import annotations

import time
from collections import Counter
from datetime import datetime
from typing import Any

from dashsys_agent.api.mock_client import MockApiClient
from dashsys_agent.api.sanitize import redact_text
from dashsys_agent.config import Settings
from dashsys_agent.db.duckdb_client import DuckDbClient
from dashsys_agent.evals.compare_results import compare_sql_results
from dashsys_agent.evals.load_samples import load_samples
from dashsys_agent.evals.normalize_api import compare_api
from dashsys_agent.evals.report import (
    write_failure_report,
    write_generalization_report,
    write_implementation_audit_report,
    write_real_api_eval_report,
)
from dashsys_agent.evals.score_answers import score_answer
from dashsys_agent.llm.lmstudio_client import LmStudioClient
from dashsys_agent.runtime.executor import make_api_client, run_query
from dashsys_agent.runtime.trajectory import validate_trajectory
from dashsys_agent.utils import write_json


def _failure_category(sql_detail: str, api_detail: str, answer_detail: str, json_ok: bool) -> str:
    if not json_ok:
        return "JSON_SCHEMA_ERROR"
    if "Generated SQL failed" in sql_detail:
        return "SQL_EXEC_ERROR"
    if "SQL row mismatch" in sql_detail or "Gold SQL" in sql_detail:
        return "SQL_RESULT_MISMATCH"
    if "generated=" in api_detail:
        return "API_ENDPOINT_MISMATCH"
    if "coverage failed" in answer_detail:
        return "ANSWER_MISMATCH"
    return "UNKNOWN"


def evaluate_samples(settings: Settings, mode: str = "A3") -> dict[str, Any]:
    samples = load_samples(settings)
    db = DuckDbClient.connect(settings)
    api_client = make_api_client(settings)
    llm_status = LmStudioClient(settings).health_check()
    failures: list[dict[str, Any]] = []
    counts: Counter[str] = Counter()
    rows: list[dict[str, Any]] = []
    start_all = time.perf_counter()
    try:
        for sample in samples:
            started = time.perf_counter()
            result = run_query(
                sample.query,
                settings,
                db=db,
                api_client=api_client,
                sample_id=sample.sample_id,
                write_artifacts=True,
            )
            runtime = time.perf_counter() - started
            json_ok = True
            json_detail = "ok"
            try:
                validate_trajectory(result.trajectory)
            except Exception as exc:
                json_ok = False
                json_detail = str(exc)
            comparison_trajectory = result.raw_trajectory or result.trajectory
            sql_result = compare_sql_results(db.con, sample.gold_sql, comparison_trajectory, settings.eval_max_rows)
            api_ok, api_detail = compare_api(sample.gold_api, comparison_trajectory)
            answer_ok, answer_score, answer_detail = score_answer(
                sample.answer,
                result.answer,
                sql_result.result_match,
                api_ok,
            )
            api_statuses = [
                step.get("api_call", {}).get("status_code")
                for step in result.trajectory.get("trace", [])
                if step.get("action") == "api_call"
            ]
            api_error_categories = [
                step.get("api_call", {}).get("error_category")
                for step in result.trajectory.get("trace", [])
                if step.get("action") == "api_call" and step.get("api_call", {}).get("error_category")
            ]
            real_api_ok = (
                True
                if settings.api_mode == "mock"
                else all(isinstance(status, int) and status < 400 for status in api_statuses)
            )
            passed = (
                json_ok
                and sql_result.exec_success
                and sql_result.result_match
                and api_ok
                and answer_ok
                and real_api_ok
            )
            row = {
                "sample_id": sample.sample_id,
                "query": sample.query,
                "json_ok": json_ok,
                "sql_exec_success": sql_result.exec_success,
                "sql_result_match": sql_result.result_match,
                "api_match": api_ok,
                "answer_coverage": answer_ok,
                "answer_score": answer_score,
                "real_api_http_success": real_api_ok,
                "api_statuses": api_statuses,
                "api_error_categories": api_error_categories,
                "tool_calls": result.metrics.tool_calls,
                "local_llm_calls": result.metrics.local_llm_calls,
                "llm_failures": result.metrics.llm_failures,
                "llm_thinking_stripped_count": result.metrics.llm_thinking_stripped_count,
                "llm_latency_seconds": result.metrics.llm_latency_seconds,
                "warnings": result.metrics.warnings,
                "runtime_seconds": runtime,
                "passed": passed,
            }
            rows.append(row)
            if not passed:
                if not real_api_ok:
                    category = "REAL_API_HTTP_ERROR"
                else:
                    category = _failure_category(sql_result.detail, api_detail, answer_detail, json_ok)
                counts[category] += 1
                likely_cause = "Planner, template, or endpoint mismatch."
                recommended_fix = "Inspect this query and add a focused deterministic rule or template correction."
                if category == "REAL_API_HTTP_ERROR":
                    likely_cause = "The live Adobe API returned one or more non-2xx statuses for whitelisted calls."
                    recommended_fix = "Inspect reports/real_api_eval_report.md, then decide whether the issue is params, endpoint path, sandbox data, permission, or Adobe transient failure."
                failures.append(
                    {
                        "sample_id": sample.sample_id,
                        "query": sample.query,
                        "expected": redact_text(
                            f"SQL: {sample.gold_sql}\nAPI: {sample.gold_api}\nAnswer: {sample.answer}",
                            settings,
                        ),
                        "predicted": result.answer,
                        "category": category,
                        "details": redact_text(
                            f"json={json_detail}; sql={sql_result.detail}; api={api_detail}; api_statuses={api_statuses}; answer={answer_detail}",
                            settings,
                        ),
                        "likely_cause": likely_cause,
                        "recommended_fix": recommended_fix,
                    }
                )
    finally:
        db.close()

    total = len(samples)
    total_runtime = time.perf_counter() - start_all
    passed_count = sum(1 for row in rows if row["passed"])
    generated_sql_rows = [row for row in rows if row["sql_exec_success"] is not None]
    fixture_hits = api_client.fixture_hits if isinstance(api_client, MockApiClient) else 0
    fixture_misses = api_client.fixture_misses if isinstance(api_client, MockApiClient) else 0
    whitelist_rejections = api_client.whitelist_rejections if isinstance(api_client, MockApiClient) else 0
    fixture_total = fixture_hits + fixture_misses
    api_status_counts = Counter(
        status
        for row in rows
        for status in row.get("api_statuses", [])
        if isinstance(status, int)
    )
    api_error_category_counts = Counter(
        category
        for row in rows
        for category in row.get("api_error_categories", [])
        if category and category != "none"
    )
    summary = {
        "mode": mode,
        "adobe_sandbox": settings.adobe_sandbox,
        "adobe_sandbox_header": settings.adobe_sandbox,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "total_samples": total,
        "passed": passed_count,
        "failed": total - passed_count,
        "json_valid_rate": sum(1 for row in rows if row["json_ok"]) / total,
        "sql_exec_success_rate": sum(1 for row in rows if row["sql_exec_success"]) / len(generated_sql_rows),
        "sql_result_match_rate": sum(1 for row in rows if row["sql_result_match"]) / total,
        "api_normalized_match_rate": sum(1 for row in rows if row["api_match"]) / total,
        "answer_evidence_coverage_rate": sum(1 for row in rows if row["answer_coverage"]) / total,
        "real_api_http_success_rate": sum(1 for row in rows if row["real_api_http_success"]) / total,
        "avg_tool_calls": sum(row["tool_calls"] for row in rows) / total,
        "avg_runtime_seconds": total_runtime / total,
        "local_llm_call_count": sum(row["local_llm_calls"] for row in rows),
        "llm_available": llm_status.available,
        "llm_model": llm_status.model,
        "llm_status_text": llm_status.status_text,
        "llm_model_text": llm_status.model_text,
        "llm_unavailable_reason": llm_status.reason,
        "llm_failures": sum(row["llm_failures"] for row in rows),
        "llm_latency_seconds": [
            *([llm_status.latency_seconds] if llm_status.latency_seconds is not None else []),
            *[latency for row in rows for latency in row.get("llm_latency_seconds", [])],
        ],
        "llm_thinking_stripped_count": sum(row["llm_thinking_stripped_count"] for row in rows),
        "mock_fixture_hit_rate": (fixture_hits / fixture_total) if fixture_total else 1.0,
        "api_whitelist_rejections": whitelist_rejections,
        "failure_count_by_category": dict(counts),
        "api_status_counts": dict(api_status_counts),
        "api_error_category_counts": dict(api_error_category_counts),
        "real_api_status_counts": dict(api_status_counts) if settings.api_mode != "mock" else {},
        "real_api_error_category_counts": dict(api_error_category_counts)
        if settings.api_mode != "mock"
        else {},
        "rows": rows,
    }
    write_failure_report(settings.repo_root / "reports" / "failure_report.md", summary, failures, settings)
    write_generalization_report(settings.repo_root / "reports" / "generalization_risks.md", summary)
    write_implementation_audit_report(settings.repo_root / "reports" / "implementation_audit.md", summary)
    write_real_api_eval_report(settings.repo_root / "reports" / "real_api_eval_report.md", summary, settings)
    write_json(settings.repo_root / "reports" / "eval_summary.json", summary)
    return summary
