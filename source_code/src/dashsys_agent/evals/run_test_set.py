from __future__ import annotations

import json
import shutil
import time
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from dashsys_agent.api.edge_cases import API_UNAVAILABLE_DUE_TO_ENTITY_STATE
from dashsys_agent.api.sanitize import redact_payload, redact_text
from dashsys_agent.config import Settings
from dashsys_agent.db.duckdb_client import DuckDbClient
from dashsys_agent.llm.lmstudio_client import LmStudioClient
from dashsys_agent.paths import ensure_inside_repo, resolve_repo_path
from dashsys_agent.runtime.executor import make_api_client, run_query
from dashsys_agent.runtime.trajectory import validate_trajectory
from dashsys_agent.utils import has_secret, read_json, write_json


def load_test_queries(path: Path) -> list[dict[str, str]]:
    payload = read_json(path)
    if isinstance(payload, dict):
        for key in ("queries", "items", "data", "test"):
            if isinstance(payload.get(key), list):
                payload = payload[key]
                break
    if not isinstance(payload, list):
        raise ValueError("Test set must be a list or a dict containing a query list")
    rows: list[dict[str, str]] = []
    for index, item in enumerate(payload, start=1):
        if isinstance(item, str):
            query = item
            test_id = f"test_{index:03d}"
        elif isinstance(item, dict) and isinstance(item.get("query"), str):
            query = item["query"]
            test_id = str(item.get("id") or item.get("query_id") or f"test_{index:03d}")
        else:
            raise ValueError(f"Invalid test query entry at position {index}")
        rows.append({"test_id": test_id, "query": query})
    return rows


def _scan_paths_for_secrets(paths: list[Path], settings: Settings) -> list[str]:
    findings: list[str] = []
    secret_values = [
        value
        for value in (
            settings.adobe_client_id,
            settings.adobe_client_secret,
            settings.adobe_ims_org,
        )
        if value and len(value) >= 6
    ]
    for root in paths:
        if not root.exists():
            continue
        candidates = [root] if root.is_file() else [path for path in root.rglob("*") if path.is_file()]
        for path in candidates:
            if path.stat().st_size > 2_000_000:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            if has_secret(text):
                findings.append(f"{path}:secret_pattern")
            for value in secret_values:
                if value in text:
                    findings.append(f"{path}:credential_value")
    return findings


def _copy_artifacts_to_submission(output_dir: Path, submission_dir: Path, summary: dict[str, Any]) -> None:
    submission_dir.mkdir(parents=True, exist_ok=True)
    for folder in ("metadata", "prompts", "trajectories", "answers"):
        source = output_dir / folder
        target = submission_dir / folder
        target.mkdir(parents=True, exist_ok=True)
        if not source.exists():
            continue
        for path in source.glob("*"):
            if path.is_file():
                shutil.copy2(path, target / path.name)
    write_json(
        submission_dir / "manifest.json",
        {
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "source_output_dir": str(output_dir),
            "format_note": (
                "Local submission-prep folder. The official page specifies per-query "
                "metadata JSON, filled prompt, and trajectory JSON. It does not define "
                "a required zip tree."
            ),
            "summary": summary,
        },
    )


def _is_handled_entity_state_failure(call: dict[str, Any]) -> bool:
    return (
        call.get("edge_case_handled") is True
        and call.get("edge_case_category") == API_UNAVAILABLE_DUE_TO_ENTITY_STATE
        and isinstance(call.get("edge_case_evidence"), dict)
    )


def classify_test_item_status(
    *,
    sql_failures: list[dict[str, Any]],
    api_calls: list[dict[str, Any]],
    mock_records: list[dict[str, Any]],
) -> dict[str, str]:
    api_failure_calls = [
        call
        for call in api_calls
        if isinstance(call.get("status_code"), int) and call["status_code"] >= 400
    ]
    whitelist_failures = [
        call
        for call in api_calls
        if call.get("error_category") == "api_whitelist_rejection"
    ]
    if sql_failures:
        return {"final_status": "failed", "root_cause": "sql_validation_or_execution"}
    if whitelist_failures:
        return {"final_status": "failed", "root_cause": "api_whitelist_rejection"}
    if mock_records:
        return {"final_status": "failed", "root_cause": "real_mode_mock_fallback"}
    if api_failure_calls:
        if all(_is_handled_entity_state_failure(call) for call in api_failure_calls):
            return {
                "final_status": "graceful_edge_case",
                "root_cause": "api_unavailable_due_to_entity_state",
            }
        return {"final_status": "failed", "root_cause": "real_api_http_error"}
    return {"final_status": "completed", "root_cause": ""}


def _write_test_set_reports(
    settings: Settings,
    summary: dict[str, Any],
    failures: list[dict[str, Any]],
) -> None:
    reports_dir = settings.repo_root / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    safe_summary = redact_payload(summary, settings)
    safe_failures = redact_payload(failures, settings)

    run_lines = [
        "# Test Set Run Report",
        "",
        f"Timestamp: {safe_summary.get('timestamp')}",
        "",
        "## Summary",
        "",
        f"- Test queries processed: {safe_summary.get('test_queries_processed')}",
        f"- Test queries handled: {safe_summary.get('test_queries_handled')}",
        f"- Test queries clean live success: {safe_summary.get('test_queries_clean_live_success')}",
        f"- Test queries graceful edge case: {safe_summary.get('test_queries_graceful_edge_case')}",
        f"- Test queries failed: {safe_summary.get('test_queries_failed')}",
        f"- SQL success count: {safe_summary.get('sql_success_count')}",
        f"- SQL failure count: {safe_summary.get('sql_failure_count')}",
        f"- API success count: {safe_summary.get('api_success_count')}",
        f"- API failure count: {safe_summary.get('api_failure_count')}",
        f"- API status counts: {safe_summary.get('api_status_counts')}",
        f"- Average tool calls: {safe_summary.get('avg_tool_calls')}",
        f"- Runtime seconds: {safe_summary.get('runtime_seconds')}",
        f"- LLM available: {safe_summary.get('llm_available')}",
        f"- LLM model: {safe_summary.get('llm_model')}",
        f"- Local LLM calls: {safe_summary.get('local_llm_calls')}",
        f"- LLM failures: {safe_summary.get('llm_failures')}",
        f"- Output folder: {safe_summary.get('output_folder')}",
        f"- Submission folder: {safe_summary.get('submission_folder')}",
        f"- Secret scan result: {safe_summary.get('secret_scan_result')}",
        "",
        "## Organizer Clarification",
        "",
        "- Organizers confirmed that the inactive batch state for test_053 is intentional.",
        "- The system should handle unavailable operations gracefully when entity state explains the API response.",
        "- This report separates clean HTTP success from evidence-backed graceful edge-case handling.",
        "",
        "## Graceful Edge Cases",
        "",
    ]
    edge_cases = safe_summary.get("edge_cases", [])
    if edge_cases:
        for edge_case in edge_cases:
            run_lines.extend(
                [
                    f"- {edge_case.get('test_id')}: {edge_case.get('category')} for "
                    f"{edge_case.get('entity_type')} {edge_case.get('entity_id')} in state "
                    f"{edge_case.get('entity_state')}; primary HTTP status "
                    f"{edge_case.get('primary_status_code')}.",
                ]
            )
    else:
        run_lines.append("- None.")
    run_lines.extend(
        [
            "",
        "## Remaining Risks",
        "",
        "- The test set has no public gold answers, so this report verifies operational completion and artifact validity, not hidden correctness.",
        "- Some SQL-only live journey questions depend on local campaign state fields. The snapshot contains no deployed journey state in the inspected rows.",
        "- New Adobe endpoint families could still fail if the official test later expects APIs outside the current strict whitelist.",
        "- The submission-prep folder is a local artifact layout, not a final CMT upload package.",
        ]
    )
    (reports_dir / "test_set_run_report.md").write_text("\n".join(run_lines) + "\n", encoding="utf-8")

    failure_lines = [
        "# Test Set Failure Report",
        "",
        f"Timestamp: {safe_summary.get('timestamp')}",
        "",
    ]
    if not safe_failures:
        failure_lines.append("No unhandled operational failures were recorded.")
        failure_lines.extend(["", "## Graceful Edge Cases", ""])
        if edge_cases:
            for edge_case in edge_cases:
                failure_lines.extend(
                    [
                        f"### {edge_case.get('test_id')}",
                        "",
                        f"Query: {edge_case.get('query')}",
                        "",
                        f"Category: {edge_case.get('category')}",
                        f"Entity: {edge_case.get('entity_type')} {edge_case.get('entity_id')}",
                        f"Entity state: {edge_case.get('entity_state')}",
                        f"Primary status: {edge_case.get('primary_status_code')}",
                        f"Supporting status: {edge_case.get('supporting_status_code')}",
                        f"Conclusion: {edge_case.get('conclusion')}",
                        "",
                    ]
                )
        else:
            failure_lines.append("None.")
    for failure in safe_failures:
        failure_lines.extend(
            [
                f"## {failure.get('test_id')}",
                "",
                f"Query: {failure.get('query')}",
                "",
                f"Intent: {failure.get('intent')}",
                f"Plan: {failure.get('plan')}",
                "",
                "SQL used:",
                failure.get("sql", ""),
                "",
                "API calls:",
                json.dumps(failure.get("api_calls", []), indent=2, ensure_ascii=False),
                "",
                f"HTTP statuses: {failure.get('http_statuses')}",
                f"Sanitized error: {failure.get('sanitized_error')}",
                f"Root cause: {failure.get('root_cause')}",
                f"Fix attempted: {failure.get('fix_attempted')}",
                f"Final status: {failure.get('final_status')}",
                "",
            ]
        )
    (reports_dir / "test_set_failure_report.md").write_text(
        "\n".join(failure_lines) + "\n",
        encoding="utf-8",
    )

    readiness_lines = [
        "# Submission Readiness",
        "",
        f"Generated at: {datetime.now().isoformat(timespec='seconds')}",
        "",
        f"- Test-set operational status: {safe_summary.get('status')}",
        f"- Test queries processed: {safe_summary.get('test_queries_processed')}/{safe_summary.get('total_queries')}",
        f"- Test queries handled: {safe_summary.get('test_queries_handled')}/{safe_summary.get('total_queries')}",
        f"- Clean live success: {safe_summary.get('test_queries_clean_live_success')}/{safe_summary.get('total_queries')}",
        f"- Graceful edge cases: {safe_summary.get('test_queries_graceful_edge_case')}/{safe_summary.get('total_queries')}",
        f"- Unhandled failures: {safe_summary.get('test_queries_failed')}/{safe_summary.get('total_queries')}",
        "- Sample real eval status: verify with `python -m dashsys_agent.cli eval-samples --api-mode real`.",
        "- Sample mock eval status: verify with `python -m dashsys_agent.cli eval-samples --api-mode mock`.",
        f"- Secret scan: {safe_summary.get('secret_scan_result')}",
        f"- Output folder: {safe_summary.get('output_folder')}",
        f"- Submission-prep folder: {safe_summary.get('submission_folder')}",
        "",
        "## Verdict",
        "",
        (
            "Ready to package after full verification passes."
            if safe_summary.get("status") == "pass"
            else "Not ready to package until failures in test_set_failure_report.md are resolved."
        ),
    ]
    (reports_dir / "submission_readiness.md").write_text(
        "\n".join(readiness_lines) + "\n",
        encoding="utf-8",
    )

    final_lines = [
        "# Final Readiness Review",
        "",
        f"Generated at: {datetime.now().isoformat(timespec='seconds')}",
        "",
        "## Test Set",
        "",
        f"- Processed: {safe_summary.get('completed')}/{safe_summary.get('total_queries')}",
        f"- Handled: {safe_summary.get('test_queries_handled')}/{safe_summary.get('total_queries')}",
        f"- Clean live success: {safe_summary.get('test_queries_clean_live_success')}/{safe_summary.get('total_queries')}",
        f"- Graceful edge cases: {safe_summary.get('test_queries_graceful_edge_case')}/{safe_summary.get('total_queries')}",
        f"- Unhandled failures: {safe_summary.get('test_queries_failed')}/{safe_summary.get('total_queries')}",
        f"- Status: {safe_summary.get('status')}",
        f"- Output folder: {safe_summary.get('output_folder')}",
        f"- Submission-prep folder: {safe_summary.get('submission_folder')}",
        f"- Secret scan: {safe_summary.get('secret_scan_result')}",
        "",
        "## Current Notes",
        "",
        "- Mock and real sample evals must be rerun after this test-set command.",
        "- Sample 33 remains documented as a live-data mismatch risk from the earlier 35-sample audit.",
        "- The official page specifies artifact types, but not an exact zip tree.",
    ]
    (reports_dir / "final_readiness_review.md").write_text(
        "\n".join(final_lines) + "\n",
        encoding="utf-8",
    )
    write_json(reports_dir / "test_set_summary.json", safe_summary)


def run_test_set(
    settings: Settings,
    input_path: Path,
    *,
    create_submission: bool = True,
) -> dict[str, Any]:
    input_path = ensure_inside_repo(resolve_repo_path(input_path))
    if settings.api_mode != "real":
        raise ValueError("run-test-set must use API_MODE=real")
    if not settings.allow_network:
        raise ValueError("run-test-set requires ALLOW_NETWORK=true")
    if settings.adobe_sandbox != "external-benchmarking":
        raise ValueError("run-test-set requires ADOBE_SANDBOX=external-benchmarking")

    test_rows = load_test_queries(input_path)
    db = DuckDbClient.connect(settings)
    api_client = make_api_client(settings)
    llm_status = LmStudioClient(settings).health_check()
    failures: list[dict[str, Any]] = []
    rows: list[dict[str, Any]] = []
    status_counts: Counter[int] = Counter()
    started_all = time.perf_counter()

    try:
        for row in test_rows:
            started = time.perf_counter()
            test_id = row["test_id"]
            query = row["query"]
            try:
                result = run_query(
                    query,
                    settings,
                    db=db,
                    api_client=api_client,
                    sample_id=test_id,
                    write_artifacts=True,
                )
                validate_trajectory(result.trajectory)
                trace = result.trajectory.get("trace", [])
                sql_steps = [step for step in trace if step.get("action") == "sql_query"]
                api_steps = [step for step in trace if step.get("action") == "api_call"]
                sql_failures = [step for step in sql_steps if step.get("status") != "success"]
                api_calls = [step.get("api_call", {}) for step in api_steps]
                http_statuses = [
                    call.get("status_code")
                    for call in api_calls
                    if isinstance(call.get("status_code"), int)
                ]
                status_counts.update(http_statuses)
                api_failures = [status for status in http_statuses if status >= 400]
                mock_records = [
                    call
                    for call in api_calls
                    if call.get("mock") or call.get("mock_fixture_miss")
                ]
                item_status = classify_test_item_status(
                    sql_failures=sql_failures,
                    api_calls=api_calls,
                    mock_records=mock_records,
                )
                final_status = item_status["final_status"]
                root_cause = item_status["root_cause"]
                runtime = time.perf_counter() - started
                item = {
                    "test_id": test_id,
                    "query": query,
                    "intent": result.metadata.get("selected_intent"),
                    "plan": result.metadata.get("selected_plan", {}).get("id"),
                    "sql_success_count": len(sql_steps) - len(sql_failures),
                    "sql_failure_count": len(sql_failures),
                    "api_call_count": len(api_calls),
                    "api_success_count": len(http_statuses) - len(api_failures),
                    "api_failure_count": len(api_failures),
                    "http_statuses": http_statuses,
                    "tool_calls": result.metrics.tool_calls,
                    "local_llm_calls": result.metrics.local_llm_calls,
                    "llm_failures": result.metrics.llm_failures,
                    "runtime_seconds": runtime,
                    "final_status": final_status,
                    "root_cause": root_cause,
                }
                rows.append(item)
                if final_status == "failed":
                    failures.append(
                        {
                            "test_id": test_id,
                            "query": query,
                            "intent": item["intent"],
                            "plan": item["plan"],
                            "sql": "\n\n".join(str(step.get("sql", "")) for step in sql_steps),
                            "api_calls": [
                                {
                                    "method": call.get("method"),
                                    "path": call.get("endpoint_path") or call.get("url"),
                                    "params": call.get("params", {}),
                                    "status_code": call.get("status_code"),
                                    "error_category": call.get("error_category"),
                                }
                                for call in api_calls
                            ],
                            "http_statuses": http_statuses,
                            "sanitized_error": redact_text(
                                "; ".join(str(call.get("message", "")) for call in api_calls if call.get("message")),
                                settings,
                            ),
                            "root_cause": root_cause,
                            "fix_attempted": "Initial full test-set run.",
                            "final_status": final_status,
                        }
                    )
            except Exception as exc:
                runtime = time.perf_counter() - started
                rows.append(
                    {
                        "test_id": test_id,
                        "query": query,
                        "intent": None,
                        "plan": None,
                        "sql_success_count": 0,
                        "sql_failure_count": 1,
                        "api_call_count": 0,
                        "api_success_count": 0,
                        "api_failure_count": 0,
                        "http_statuses": [],
                        "tool_calls": 0,
                        "local_llm_calls": 0,
                        "llm_failures": 0,
                        "runtime_seconds": runtime,
                        "final_status": "failed",
                        "root_cause": "code_exception",
                    }
                )
                failures.append(
                    {
                        "test_id": test_id,
                        "query": query,
                        "intent": None,
                        "plan": None,
                        "sql": "",
                        "api_calls": [],
                        "http_statuses": [],
                        "sanitized_error": redact_text(str(exc), settings),
                        "root_cause": "code_exception",
                        "fix_attempted": "Initial full test-set run.",
                        "final_status": "failed",
                    }
                )
    finally:
        db.close()

    runtime_all = time.perf_counter() - started_all
    timestamp = settings.output_dir.name
    submission_dir = settings.repo_root / "submission" / "test_set" / timestamp if create_submission else None
    edge_cases: list[dict[str, Any]] = []
    for row in rows:
        if row.get("final_status") != "graceful_edge_case":
            continue
        test_id = str(row.get("test_id"))
        trajectory_path = settings.output_dir / "trajectories" / f"{test_id}.json"
        trajectory = read_json(trajectory_path) if trajectory_path.exists() else {}
        for step in trajectory.get("trace", []):
            call = step.get("api_call", {}) if step.get("action") == "api_call" else {}
            edge = call.get("edge_case_evidence")
            if isinstance(edge, dict):
                edge_cases.append(
                    {
                        "test_id": test_id,
                        "query": row.get("query"),
                        **edge,
                    }
                )
                break
    clean_live_success_count = sum(1 for row in rows if row["final_status"] == "completed")
    graceful_edge_case_count = sum(1 for row in rows if row["final_status"] == "graceful_edge_case")
    failed_count = sum(1 for row in rows if row["final_status"] == "failed")
    handled_count = clean_live_success_count + graceful_edge_case_count
    summary: dict[str, Any] = {
        "timestamp": timestamp,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "api_mode": settings.api_mode,
        "adobe_sandbox_header": settings.adobe_sandbox,
        "input_path": str(input_path),
        "total_queries": len(test_rows),
        "test_queries_processed": len(test_rows),
        "test_queries_handled": handled_count,
        "test_queries_clean_live_success": clean_live_success_count,
        "test_queries_graceful_edge_case": graceful_edge_case_count,
        "test_queries_failed": failed_count,
        "completed": handled_count,
        "failed": failed_count,
        "sql_success_count": sum(row["sql_success_count"] for row in rows),
        "sql_failure_count": sum(row["sql_failure_count"] for row in rows),
        "api_success_count": sum(row["api_success_count"] for row in rows),
        "api_failure_count": sum(row["api_failure_count"] for row in rows),
        "api_status_counts": dict(status_counts),
        "avg_tool_calls": (sum(row["tool_calls"] for row in rows) / len(rows)) if rows else 0,
        "runtime_seconds": runtime_all,
        "llm_available": llm_status.available,
        "llm_model": llm_status.model,
        "local_llm_calls": sum(row["local_llm_calls"] for row in rows),
        "llm_failures": sum(row["llm_failures"] for row in rows),
        "output_folder": str(settings.output_dir),
        "submission_folder": str(submission_dir) if submission_dir else None,
        "edge_cases": edge_cases,
        "rows": rows,
    }
    summary["status"] = "pass" if summary["failed"] == 0 else "fail"
    if submission_dir:
        _copy_artifacts_to_submission(settings.output_dir, submission_dir, redact_payload(summary, settings))
    scan_paths = [settings.output_dir]
    if submission_dir:
        scan_paths.append(submission_dir)
    secret_findings = _scan_paths_for_secrets(scan_paths, settings)
    summary["secret_scan_findings"] = secret_findings
    summary["secret_scan_result"] = "clean" if not secret_findings else "fail"
    if secret_findings:
        summary["status"] = "fail"
        failures.append(
            {
                "test_id": "secret_scan",
                "query": "",
                "intent": None,
                "plan": None,
                "sql": "",
                "api_calls": [],
                "http_statuses": [],
                "sanitized_error": "Generated artifact secret scan failed.",
                "root_cause": "secret_leak_risk",
                "fix_attempted": "Secret scan after test-set run.",
                "final_status": "failed",
            }
        )
    _write_test_set_reports(settings, summary, failures)
    report_findings = _scan_paths_for_secrets(
        [
            settings.repo_root / "reports" / "test_set_run_report.md",
            settings.repo_root / "reports" / "test_set_failure_report.md",
            settings.repo_root / "reports" / "submission_readiness.md",
            settings.repo_root / "reports" / "final_readiness_review.md",
            settings.repo_root / "reports" / "test_set_summary.json",
        ],
        settings,
    )
    if report_findings:
        summary["secret_scan_findings"] = [*secret_findings, *report_findings]
        summary["secret_scan_result"] = "fail"
        summary["status"] = "fail"
        failures.append(
            {
                "test_id": "report_secret_scan",
                "query": "",
                "intent": None,
                "plan": None,
                "sql": "",
                "api_calls": [],
                "http_statuses": [],
                "sanitized_error": "Generated report secret scan failed.",
                "root_cause": "secret_leak_risk",
                "fix_attempted": "Secret scan after report generation.",
                "final_status": "failed",
            }
        )
        _write_test_set_reports(settings, summary, failures)
    return redact_payload(summary, settings)
