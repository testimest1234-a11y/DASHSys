from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv

from dashsys_agent.paths import ensure_inside_repo, repo_root, resolve_repo_path
from dashsys_agent.utils import normalize_bool


@dataclass(frozen=True)
class Settings:
    repo_root: Path
    app_env: str
    debug: bool
    snapshot_dir: Path
    samples_path: Path
    output_dir: Path
    llm_enabled: bool
    llm_provider: str
    llm_base_url: str
    llm_api_key: str
    llm_model: str
    llm_temperature: float
    llm_max_tokens: int
    llm_timeout_seconds: int
    local_llm_strict: bool
    api_mode: str
    allow_network: bool
    adobe_base_url: str
    adobe_ims_token_url: str
    adobe_client_id: str
    adobe_client_secret: str
    adobe_ims_org: str
    adobe_sandbox: str
    eval_max_rows: int
    eval_fail_on_json_error: bool

    @property
    def catalog_dir(self) -> Path:
        return self.output_dir / "catalog"

    @property
    def schema_catalog_path(self) -> Path:
        return self.catalog_dir / "schema_catalog.json"

    @property
    def join_graph_path(self) -> Path:
        return self.catalog_dir / "join_graph.json"


def ensure_env_file() -> None:
    env_path = repo_root() / ".env"
    example_path = repo_root() / ".env.example"
    if not env_path.exists() and example_path.exists():
        env_path.write_text(example_path.read_text(encoding="utf-8"), encoding="utf-8")


def _env(name: str, default: str = "") -> str:
    import os

    return os.environ.get(name, default)


def _validate_local_llm_url(base_url: str, strict: bool) -> None:
    if not strict:
        return
    parsed = urlparse(base_url)
    host = (parsed.hostname or "").lower()
    if host not in {"localhost", "127.0.0.1", "::1"}:
        raise ValueError(f"LLM_BASE_URL must point to localhost in strict mode: {base_url}")
    blocked = ("api.openai.com", "anthropic.com", "generativelanguage.googleapis.com")
    if any(block in base_url.lower() for block in blocked):
        raise ValueError("Paid remote LLM endpoints are not allowed")


def load_settings(overrides: dict[str, str] | None = None) -> Settings:
    ensure_env_file()
    load_dotenv(repo_root() / ".env", override=False)
    overrides = overrides or {}

    def value(name: str, default: str = "") -> str:
        return overrides.get(name, _env(name, default))

    local_llm_strict = normalize_bool(value("LOCAL_LLM_STRICT", "true"), True)
    llm_base_url = value("LLM_BASE_URL", "http://localhost:1234/v1")
    _validate_local_llm_url(llm_base_url, local_llm_strict)

    root = repo_root()
    snapshot_dir = ensure_inside_repo(resolve_repo_path(value("SNAPSHOT_DIR", "data/DBSnapshot")))
    samples_path = ensure_inside_repo(resolve_repo_path(value("SAMPLES_PATH", "data/data.json")))
    output_dir = ensure_inside_repo(resolve_repo_path(value("OUTPUT_DIR", "outputs")))
    api_mode = value("API_MODE", "mock").lower()
    allow_network = normalize_bool(value("ALLOW_NETWORK", "false"), False)
    if api_mode == "mock" and allow_network:
        raise ValueError("ALLOW_NETWORK must be false in mock mode")
    if api_mode not in {"mock", "real", "record"}:
        raise ValueError(f"Unsupported API_MODE: {api_mode}")

    return Settings(
        repo_root=root,
        app_env=value("APP_ENV", "local"),
        debug=normalize_bool(value("DEBUG", "false"), False),
        snapshot_dir=snapshot_dir,
        samples_path=samples_path,
        output_dir=output_dir,
        llm_enabled=normalize_bool(value("LLM_ENABLED", "true"), True),
        llm_provider=value("LLM_PROVIDER", "lmstudio"),
        llm_base_url=llm_base_url.rstrip("/"),
        llm_api_key=value("LLM_API_KEY", "lm-studio"),
        llm_model=value("LLM_MODEL", "qwen/qwen3.5-9b"),
        llm_temperature=float(value("LLM_TEMPERATURE", "0")),
        llm_max_tokens=int(value("LLM_MAX_TOKENS", "512")),
        llm_timeout_seconds=int(value("LLM_TIMEOUT_SECONDS", "120")),
        local_llm_strict=local_llm_strict,
        api_mode=api_mode,
        allow_network=allow_network,
        adobe_base_url=value("ADOBE_BASE_URL", "https://platform.adobe.io").rstrip("/"),
        adobe_ims_token_url=value("ADOBE_IMS_TOKEN_URL", "https://ims-na1.adobelogin.com/ims/token/v3"),
        adobe_client_id=value("ADOBE_CLIENT_ID", ""),
        adobe_client_secret=value("ADOBE_CLIENT_SECRET", ""),
        adobe_ims_org=value("ADOBE_IMS_ORG", ""),
        adobe_sandbox=value("ADOBE_SANDBOX", ""),
        eval_max_rows=int(value("EVAL_MAX_ROWS", "500")),
        eval_fail_on_json_error=normalize_bool(value("EVAL_FAIL_ON_JSON_ERROR", "true"), True),
    )
