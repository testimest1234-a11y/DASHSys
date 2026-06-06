from __future__ import annotations

from datetime import datetime

from dashsys_agent.config import Settings
from dashsys_agent.evals.eval_samples import evaluate_samples
from dashsys_agent.evals.report import append_ablation_row

MODES = [
    ("A0", "Deterministic router plus SQL templates only"),
    ("A1", "A0 plus fuzzy entity matching"),
    ("A2", "A1 plus SQL validation"),
    ("A3", "A2 plus mock API fixtures"),
    ("A4", "A3 plus local LLM plan chooser for ambiguous cases"),
    ("A5", "A4 plus optional local LLM answer polish"),
]


def run_ablation(settings: Settings) -> list[dict]:
    rows = []
    for mode, notes in MODES:
        summary = evaluate_samples(settings, mode=mode)
        row = {
            "run_id": mode,
            "mode": mode,
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "json_valid_rate": summary["json_valid_rate"],
            "sql_exec_success_rate": summary["sql_exec_success_rate"],
            "sql_result_match_rate": summary["sql_result_match_rate"],
            "api_normalized_match_rate": summary["api_normalized_match_rate"],
            "answer_evidence_coverage_rate": summary["answer_evidence_coverage_rate"],
            "avg_tool_calls": summary["avg_tool_calls"],
            "avg_runtime_seconds": summary["avg_runtime_seconds"],
            "local_llm_calls": summary["local_llm_call_count"],
            "llm_available": summary["llm_available"],
            "llm_model": summary["llm_model"],
            "llm_failures": summary["llm_failures"],
            "llm_thinking_stripped_count": summary["llm_thinking_stripped_count"],
            "mock_fixture_hit_rate": summary["mock_fixture_hit_rate"],
            "notes": notes,
        }
        append_ablation_row(settings.repo_root / "reports" / "ablation_results.csv", row)
        rows.append(row)
    return rows
