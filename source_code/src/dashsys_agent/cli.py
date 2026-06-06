from __future__ import annotations

import argparse
import json
import platform
import sys
from pathlib import Path
from typing import Any

import duckdb

from dashsys_agent.api.auth import credential_status
from dashsys_agent.api.health import real_api_health_check
from dashsys_agent.api.sanitize import redact_payload
from dashsys_agent.config import load_settings
from dashsys_agent.db.duckdb_client import DuckDbClient
from dashsys_agent.db.join_graph import build_join_graph
from dashsys_agent.db.parquet_loader import parquet_files, register_parquet_views
from dashsys_agent.db.schema_catalog import build_schema_catalog
from dashsys_agent.evals.ablate import run_ablation
from dashsys_agent.evals.eval_samples import evaluate_samples
from dashsys_agent.evals.report import write_real_api_health_report
from dashsys_agent.evals.run_test_set import run_test_set
from dashsys_agent.llm.lmstudio_client import LmStudioClient
from dashsys_agent.runtime.executor import run_query
from dashsys_agent.utils import has_secret, write_json


def _print(payload: Any) -> None:
    print(json.dumps(payload, indent=2, ensure_ascii=False))


def _scan_generated_for_secrets(root: Path, settings: Any | None = None) -> list[str]:
    findings = []
    secret_needles: dict[str, str] = {}
    if settings:
        for label, value in {
            "ADOBE_CLIENT_ID": settings.adobe_client_id,
            "ADOBE_CLIENT_SECRET": settings.adobe_client_secret,
            "ADOBE_IMS_ORG": settings.adobe_ims_org,
        }.items():
            if value and len(value) >= 6:
                secret_needles[label] = value
    for folder in (root / "outputs", root / "reports", root / "logs"):
        if not folder.exists():
            continue
        for path in folder.rglob("*"):
            if path.is_file() and path.stat().st_size < 2_000_000:
                text = path.read_text(encoding="utf-8", errors="ignore")
                if has_secret(text):
                    findings.append(f"{path}:secret_pattern")
                for label, value in secret_needles.items():
                    if value in text:
                        findings.append(f"{path}:{label}")
    return findings


def cmd_doctor(_: argparse.Namespace) -> int:
    settings = load_settings()
    checks: list[dict[str, Any]] = []
    errors = 0

    def check(name: str, ok: bool, detail: str = "", warning: bool = False) -> None:
        nonlocal errors
        checks.append({"name": name, "ok": ok, "warning": warning, "detail": detail})
        if not ok and not warning:
            errors += 1

    check("cwd", Path.cwd().resolve() == settings.repo_root.resolve(), f"cwd={Path.cwd()}")
    check("python_version", sys.version_info >= (3, 10), platform.python_version())
    check("env_file", (settings.repo_root / ".env").exists(), ".env exists or was created from .env.example")
    check("samples_path", settings.samples_path.exists(), str(settings.samples_path))
    check("snapshot_dir", settings.snapshot_dir.exists(), str(settings.snapshot_dir))
    files = parquet_files(settings.snapshot_dir) if settings.snapshot_dir.exists() else []
    check("parquet_count", len(files) > 0, f"{len(files)} parquet files")
    try:
        con = duckdb.connect(database=":memory:")
        tables = register_parquet_views(con, settings.snapshot_dir)
        check("duckdb_register_views", len(tables) == len(files), f"registered {len(tables)} views")
        con.close()
    except Exception as exc:
        check("duckdb_register_views", False, str(exc))
    api_status_payload = {
        "api_mode_text": f"API mode: {settings.api_mode}",
        "adobe_sandbox_text": f"Adobe sandbox header: {settings.adobe_sandbox}",
    }
    check("api_mode", settings.api_mode == "mock" or settings.api_mode in {"real", "record"}, settings.api_mode)
    check("allow_network", not (settings.api_mode == "mock" and settings.allow_network), f"ALLOW_NETWORK={settings.allow_network}")
    if settings.api_mode == "real":
        status = credential_status(settings)
        detail = "Adobe credentials: present" if status.present else f"missing={status.missing}"
        check("real_api_credentials", status.present, detail)
        api_status_payload["adobe_credentials_text"] = (
            "Adobe credentials: present" if status.present else "Adobe credentials: missing"
        )
    llm_status_payload = {}
    if settings.llm_enabled:
        status = LmStudioClient(settings).health_check()
        available = status.available
        detail = (
            f"{status.status_text}; {status.model_text}; latency={status.latency_seconds:.3f}s"
            if available
            else f"{status.status_text}; Reason: {status.reason}; Running deterministic mode only"
        )
        check("lm_studio", available, detail, warning=not available)
        llm_status_payload = {
            "llm_available": status.available,
            "llm_model": status.model,
            "llm_status_text": status.status_text,
            "llm_model_text": status.model_text,
            "llm_unavailable_reason": status.reason,
        }
    secret_findings = _scan_generated_for_secrets(settings.repo_root, settings)
    check("secret_scan", not secret_findings, f"findings={secret_findings}")
    _print({"status": "pass" if errors == 0 else "fail", **api_status_payload, **llm_status_payload, "checks": checks})
    return 0 if errors == 0 else 1


def cmd_build_catalog(_: argparse.Namespace) -> int:
    settings = load_settings()
    db = DuckDbClient.connect(settings)
    try:
        catalog = build_schema_catalog(db.con, db.tables)
        join_graph = build_join_graph(catalog)
        catalog = redact_payload(catalog, settings)
        join_graph = redact_payload(join_graph, settings)
        write_json(settings.schema_catalog_path, catalog)
        write_json(settings.join_graph_path, join_graph)
        _print(
            {
                "tables": len(catalog["tables"]),
                "joins": len(join_graph["joins"]),
                "schema_catalog": str(settings.schema_catalog_path),
                "join_graph": str(settings.join_graph_path),
            }
        )
        return 0
    finally:
        db.close()


def cmd_run(args: argparse.Namespace) -> int:
    overrides = {}
    if args.api_mode:
        overrides = {"API_MODE": args.api_mode, "ALLOW_NETWORK": "false" if args.api_mode == "mock" else "true"}
    settings = load_settings(overrides)
    result = run_query(args.query, settings)
    _print(redact_payload(result.trajectory, settings))
    return 0


def cmd_eval_samples(args: argparse.Namespace) -> int:
    overrides = {"API_MODE": args.api_mode, "ALLOW_NETWORK": "false" if args.api_mode == "mock" else "true"}
    settings = load_settings(overrides)
    summary = evaluate_samples(settings, mode=args.api_mode)
    _print({key: value for key, value in summary.items() if key != "rows"})
    thresholds_ok = (
        summary["json_valid_rate"] == 1.0
        and summary["sql_exec_success_rate"] == 1.0
        and summary["api_whitelist_rejections"] == 0
    )
    return 0 if thresholds_ok else 1


def cmd_api_health(_: argparse.Namespace) -> int:
    settings = load_settings()
    report = redact_payload(real_api_health_check(settings), settings)
    write_real_api_health_report(settings.repo_root / "reports" / "real_api_health.md", report, settings)
    _print(report)
    return 0 if report.get("auth", {}).get("auth_status") == "pass" else 1


def cmd_run_test_set(args: argparse.Namespace) -> int:
    timestamp = args.timestamp or datetime_now_slug()
    overrides = {
        "API_MODE": args.api_mode,
        "ALLOW_NETWORK": "true",
        "OUTPUT_DIR": f"outputs/test_set/{timestamp}",
    }
    settings = load_settings(overrides)
    summary = run_test_set(settings, Path(args.input), create_submission=not args.no_submission_folder)
    _print({key: value for key, value in summary.items() if key != "rows"})
    return 0 if summary.get("status") == "pass" else 1


def cmd_ablate(_: argparse.Namespace) -> int:
    settings = load_settings({"API_MODE": "mock", "ALLOW_NETWORK": "false"})
    rows = run_ablation(settings)
    _print(rows)
    return 0


def datetime_now_slug() -> str:
    from datetime import datetime

    return datetime.now().strftime("%Y%m%d_%H%M%S")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="dashsys_agent")
    sub = parser.add_subparsers(required=True)
    doctor = sub.add_parser("doctor")
    doctor.set_defaults(func=cmd_doctor)
    catalog = sub.add_parser("build-catalog")
    catalog.set_defaults(func=cmd_build_catalog)
    run = sub.add_parser("run")
    run.add_argument("--query", required=True)
    run.add_argument("--api-mode", choices=["mock", "real", "record"])
    run.set_defaults(func=cmd_run)
    eval_samples = sub.add_parser("eval-samples")
    eval_samples.add_argument("--api-mode", default="mock", choices=["mock", "real", "record"])
    eval_samples.set_defaults(func=cmd_eval_samples)
    ablate = sub.add_parser("ablate")
    ablate.set_defaults(func=cmd_ablate)
    api_health = sub.add_parser("api-health")
    api_health.set_defaults(func=cmd_api_health)
    run_test = sub.add_parser("run-test-set")
    run_test.add_argument("--input", required=True)
    run_test.add_argument("--api-mode", default="real", choices=["real"])
    run_test.add_argument("--timestamp")
    run_test.add_argument("--no-submission-folder", action="store_true")
    run_test.set_defaults(func=cmd_run_test_set)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
