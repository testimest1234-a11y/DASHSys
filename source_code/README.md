# DASHSys Local-First Agent

This repo contains a deterministic-heavy Python agent for the DASHSys 2026 Real-World Systems Track. It answers natural-language questions using local DuckDB queries over parquet files and safe Adobe API calls through mock fixtures by default.

## Safety Defaults

- DuckDB reads `data/DBSnapshot/*.parquet` in memory.
- `API_MODE=mock` and `ALLOW_NETWORK=false` by default.
- Adobe credentials are not required for local evaluation.
- LM Studio is optional and must be local at `http://localhost:1234/v1`.
- Paid remote LLM APIs are not used.

## Setup on Windows

```powershell
cd .\dashsys-agent
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install -e .
Copy-Item .env.example .env
```

If activation is blocked:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

## Commands

```powershell
python -m dashsys_agent.cli doctor
python -m dashsys_agent.cli build-catalog
python -m dashsys_agent.cli run --query "List all journeys"
python -m dashsys_agent.cli eval-samples --api-mode mock
python -m dashsys_agent.cli eval-samples --api-mode real
python -m dashsys_agent.cli run-test-set --input data/test.json --api-mode real
python -m dashsys_agent.cli ablate
```

## Architecture

The runtime normalizes the query, extracts entities, selects a deterministic plan, renders SQL from templates, validates SQL, executes DuckDB queries, validates API calls against a whitelist, calls mock fixtures, merges evidence, writes artifacts, and validates the trajectory JSON.

LM Studio can only choose from existing plan IDs for ambiguous cases. It cannot invent SQL, table names, columns, endpoints, credentials, or final facts.

## Local LLM Health

The current local model target is `qwen/qwen3.5-9b` through LM Studio at:

```text
http://localhost:1234/v1
```

Before any optional local LLM use, the system checks:

```text
GET http://localhost:1234/v1/models
```

`doctor`, `eval-samples`, runtime logs, and eval reports include:

- `llm_available`
- `llm_model`
- `local_llm_calls`
- `llm_failures`
- `llm_latency_seconds`
- `llm_thinking_stripped_count`

If LM Studio is unavailable, the system reports the reason and runs deterministic mode only. Local LLM outputs may include thinking text, so the parser extracts only the final bounded JSON and never saves thinking text to trajectories, reports, prompts, answers, or submitted artifacts.

## Outputs

Runtime artifacts are written under `outputs/`:

- `metadata/`
- `prompts/`
- `trajectories/`
- `answers/`
- `catalog/schema_catalog.json`
- `catalog/join_graph.json`

Reports are written under `reports/`:

- `failure_report.md`
- `ablation_results.csv`
- `generalization_risks.md`
- `implementation_audit.md`
- `real_api_health.md`
- `real_api_eval_report.md`
- `real_api_fix_log.md`
- `final_readiness_review.md`
- `test_set_run_report.md`
- `test_set_failure_report.md`
- `submission_readiness.md`

These generated folders are ignored by Git.

Official test-set artifacts are written under timestamped folders:

- `outputs/test_set/<timestamp>/metadata/`
- `outputs/test_set/<timestamp>/prompts/`
- `outputs/test_set/<timestamp>/trajectories/`
- `outputs/test_set/<timestamp>/answers/`

The CLI also creates a local submission-prep mirror under `submission/test_set/<timestamp>/`. This is a prepared local artifact layout, not a final CMT upload package.

## Real Adobe API Mode

Real mode is disabled by default. Set these in `.env` only when credentials exist and network use is intended:

```env
API_MODE=real
ALLOW_NETWORK=true
ADOBE_CLIENT_ID=
ADOBE_CLIENT_SECRET=
ADOBE_IMS_ORG=
ADOBE_SANDBOX=
```

The credential email sandbox label is `Adobe PEAK Program`, but the official DASHSys task page says the API request header should use `external-benchmarking`. In live testing, `external-benchmarking` improved `/ajo/journey` from HTTP 500 to HTTP 200. After endpoint and parameter fixes, real eval improved from 23/35 to 35/35 live HTTP success.

Real API readiness can be checked with:

```powershell
python -m dashsys_agent.cli api-health
```

The client uses IMS client-credentials auth, keeps the access token in memory only, retries once for transient `429` or `5xx`, and redacts sensitive headers, tokens, client IDs, client secrets, and IMS org IDs before writing logs, reports, trajectories, prompts, or answers.

Real mode includes strict adaptations for live Adobe API shapes found during verification:

- Schema Registry media-type Accept headers.
- `/schemas` sample shortcut mapping to Schema Registry.
- Schema placeholder resolution from SQL or prior API evidence.
- `/audit/events` sample shortcut mapping to the full Audit endpoint.
- Unified Tags routing to `https://experience.adobe.io`.
- Failed export batch lookup through `/files?status=failed`.

## Current Status

Latest mock evaluation:

- 35 of 35 samples passed.
- JSON validity, SQL execution, SQL result match, API normalized match, and evidence coverage are all 100%.
- Average tool calls: 1.54.
- Local LLM calls: 0.

Latest real API check:

- IMS auth passes.
- Sandbox header reported: `external-benchmarking`.
- Safe `/ajo/journey` GET returns HTTP 200.
- Real eval ran all 35 samples and 35 passed the live HTTP gate.
- Real API status counts: HTTP 200 = 39.
- Remaining live API failures: 0.

Latest official test-set run:

- Test queries processed: 60/60.
- Test queries handled: 60/60.
- Clean live success: 59/60.
- Graceful edge cases: 1/60.
- Unhandled failures: 0/60.
- Recommended deterministic submission-prep folder: `submission/test_set/20260605_052613`.
- `test_053` is handled as `API_UNAVAILABLE_DUE_TO_ENTITY_STATE`, where the batch exists in Catalog but Data Access failed-file listing is unavailable because the batch is inactive or not listable through that endpoint.
- Long observability metric ranges are split into API-accepted date windows.
- Latest LM Studio available test-set comparison made 0 local LLM calls and did not improve answers, so deterministic output remains recommended.
- Secret scan result: clean.

This is an evaluator result, not proof of hidden-test performance. Known risks are documented in `reports/generalization_risks.md` and `reports/real_api_eval_report.md`.
