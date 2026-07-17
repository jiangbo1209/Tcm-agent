"""Agent configuration."""

from __future__ import annotations

from dataclasses import dataclass
from os import getenv
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _read_dotenv() -> dict[str, str]:
    env_path = PROJECT_ROOT / ".env"
    if not env_path.exists():
        return {}

    values: dict[str, str] = {}
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


_DOTENV = _read_dotenv()


def _env(name: str, default: str = "") -> str:
    return getenv(name) or _DOTENV.get(name, default)


def _env_int(name: str, default: int) -> int:
    return int(_env(name, str(default)))


def _env_float(name: str, default: float) -> float:
    return float(_env(name, str(default)))


def _env_bool(name: str, default: bool) -> bool:
    raw = _env(name, str(default)).lower()
    return raw in {"1", "true", "yes", "on"}


@dataclass(frozen=True, slots=True)
class AgentSettings:
    default_top_k: int = _env_int("AGENT_DEFAULT_TOP_K", 6)
    retrieval_timeout_seconds: int = _env_int("RAGFLOW_REQUEST_TIMEOUT", 30)
    enable_guideline_validation: bool = _env_bool("AGENT_ENABLE_GUIDELINE_VALIDATION", False)
    enable_guideline_retrieval: bool = _env_bool("AGENT_ENABLE_GUIDELINE_RETRIEVAL", False)

    llm_provider: str = _env("LLM_PROVIDER", "openai")
    llm_base_url: str = _env("LLM_BASE_URL", "")
    llm_api_key: str = _env("LLM_API_KEY", _env("RELAY_API_KEY", ""))
    llm_model: str = _env("LLM_MODEL", "qwen-plus")
    llm_auth_header: str = _env("LLM_AUTH_HEADER", "Authorization")
    llm_timeout_seconds: int = _env_int("LLM_TIMEOUT_SECONDS", 120)
    llm_temperature: float = _env_float("LLM_TEMPERATURE", 0.2)
    llm_max_tokens: int = _env_int("LLM_MAX_TOKENS", 4096)
    enable_llm_query_analysis: bool = _env_bool("AGENT_ENABLE_LLM_QUERY_ANALYSIS", False)

    memory_recent_message_limit: int = _env_int("AGENT_MEMORY_RECENT_MESSAGE_LIMIT", 8)
    memory_summary_max_chars: int = _env_int("AGENT_MEMORY_SUMMARY_MAX_CHARS", 4000)

    ragflow_base_url: str = _env("RAGFLOW_BASE_URL", "http://127.0.0.1:9380")
    ragflow_api_key: str = _env("RAGFLOW_API_KEY", "")
    ragflow_literature_dataset_id: str = _env("RAGFLOW_LITERATURE_DATASET_ID", "")
    ragflow_case_dataset_id: str = _env("RAGFLOW_CASE_DATASET_ID", "")
    ragflow_guideline_dataset_id: str = _env("RAGFLOW_GUIDELINE_DATASET_ID", "")
    ragflow_similarity_threshold: float = _env_float("RAGFLOW_SIMILARITY_THRESHOLD", 0.2)
    ragflow_vector_similarity_weight: float = _env_float("RAGFLOW_VECTOR_SIMILARITY_WEIGHT", 0.3)
    ragflow_top_k_candidates: int = _env_int("RAGFLOW_TOP_K", 1024)
    ragflow_keyword: bool = _env_bool("RAGFLOW_KEYWORD", True)
    ragflow_highlight: bool = _env_bool("RAGFLOW_HIGHLIGHT", False)
    ragflow_use_kg: bool = _env_bool("RAGFLOW_USE_KG", False)
    ragflow_toc_enhance: bool = _env_bool("RAGFLOW_TOC_ENHANCE", False)


def get_agent_settings() -> AgentSettings:
    return AgentSettings()
