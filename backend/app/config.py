"""Central configuration.

Every setting can be supplied through environment variables or a `.env` file
in the `backend/` folder. A few of them (thresholds, top-k, ...) can also be
changed at runtime from the Settings page of the UI via `PUT /api/config`.
"""
from __future__ import annotations

import os
from dataclasses import asdict, dataclass, field
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BACKEND_DIR / ".env")


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def _env_float(name: str, default: float) -> float:
    try:
        return float(_env(name, str(default)))
    except ValueError:
        return default


def _env_int(name: str, default: int) -> int:
    try:
        return int(_env(name, str(default)))
    except ValueError:
        return default


def _env_bool(name: str, default: bool) -> bool:
    v = _env(name, str(default)).lower()
    return v in {"1", "true", "yes", "on"}


# Sensible defaults for every OpenAI-compatible provider we support.
PROVIDER_DEFAULTS = {
    "groq": ("https://api.groq.com/openai/v1", "openai/gpt-oss-120b"),
    "openai": ("https://api.openai.com/v1", "gpt-4o-mini"),
    "gemini": ("https://generativelanguage.googleapis.com/v1beta/openai/", "gemini-2.5-flash"),
    "ollama": ("http://localhost:11434/v1", "llama3.1"),
    "openrouter": ("https://openrouter.ai/api/v1", "meta-llama/llama-3.3-70b-instruct"),
    "mock": ("", "mock-llm"),
}


@dataclass
class Settings:
    # ---------- LLM ----------
    llm_provider: str = field(default_factory=lambda: _env("LLM_PROVIDER", "mock").lower())
    llm_api_key: str = field(default_factory=lambda: _env("LLM_API_KEY"))
    llm_base_url: str = field(default_factory=lambda: _env("LLM_BASE_URL"))
    llm_model: str = field(default_factory=lambda: _env("LLM_MODEL"))
    llm_temperature: float = field(default_factory=lambda: _env_float("LLM_TEMPERATURE", 0.0))
    llm_max_workers: int = field(default_factory=lambda: _env_int("LLM_MAX_WORKERS", 4))

    # ---------- Embeddings / vector DB ----------
    embedding_backend: str = field(default_factory=lambda: _env("EMBEDDING_BACKEND", "auto").lower())
    embedding_model: str = field(default_factory=lambda: _env("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"))
    chroma_dir: str = field(default_factory=lambda: _env("CHROMA_DIR", str(BACKEND_DIR / "storage" / "chroma")))
    chunk_size: int = field(default_factory=lambda: _env_int("CHUNK_SIZE", 800))
    chunk_overlap: int = field(default_factory=lambda: _env_int("CHUNK_OVERLAP", 120))

    # ---------- Retrieval evaluator & router ----------
    # llm | cross_encoder | embedding
    evaluator_backend: str = field(default_factory=lambda: _env("EVALUATOR_BACKEND", "llm").lower())
    cross_encoder_model: str = field(default_factory=lambda: _env("CROSS_ENCODER_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2"))
    top_k: int = field(default_factory=lambda: _env_int("TOP_K", 4))
    upper_threshold: float = field(default_factory=lambda: _env_float("UPPER_THRESHOLD", 0.7))
    lower_threshold: float = field(default_factory=lambda: _env_float("LOWER_THRESHOLD", 0.3))
    max_rewrites: int = field(default_factory=lambda: _env_int("MAX_REWRITES", 1))
    enable_refinement: bool = field(default_factory=lambda: _env_bool("ENABLE_REFINEMENT", True))
    strip_threshold: float = field(default_factory=lambda: _env_float("STRIP_THRESHOLD", 0.15))

    # ---------- Web search ----------
    # tavily | duckduckgo | none   (auto = tavily if key present, else duckduckgo)
    web_search_provider: str = field(default_factory=lambda: _env("WEB_SEARCH_PROVIDER", "auto").lower())
    tavily_api_key: str = field(default_factory=lambda: _env("TAVILY_API_KEY"))
    web_results: int = field(default_factory=lambda: _env_int("WEB_RESULTS", 4))
    web_timeout: float = field(default_factory=lambda: _env_float("WEB_TIMEOUT", 20))

    # ---------- Answer validation ----------
    enable_validation: bool = field(default_factory=lambda: _env_bool("ENABLE_VALIDATION", True))
    max_validation_retries: int = field(default_factory=lambda: _env_int("MAX_VALIDATION_RETRIES", 1))
    validation_threshold: float = field(default_factory=lambda: _env_float("VALIDATION_THRESHOLD", 0.6))

    def __post_init__(self) -> None:
        base, model = PROVIDER_DEFAULTS.get(self.llm_provider, ("", ""))
        self.llm_base_url = self.llm_base_url or base
        self.llm_model = self.llm_model or model
        self.embedding_backend = self.embedding_backend.replace("-", "_")
        if self.web_search_provider == "auto":
            self.web_search_provider = "tavily" if self.tavily_api_key else "duckduckgo"

    # Fields that the UI is allowed to change at runtime.
    RUNTIME_FIELDS = (
        "top_k", "upper_threshold", "lower_threshold", "max_rewrites",
        "enable_refinement", "strip_threshold", "web_search_provider",
        "web_results", "enable_validation", "max_validation_retries",
        "validation_threshold", "evaluator_backend",
    )

    def public(self) -> dict:
        d = asdict(self)
        d.pop("llm_api_key", None)
        d.pop("tavily_api_key", None)
        d["llm_key_set"] = bool(self.llm_api_key)
        d["tavily_key_set"] = bool(self.tavily_api_key)
        return d

    def update(self, values: dict) -> None:
        for k, v in values.items():
            if k in self.RUNTIME_FIELDS and v is not None:
                setattr(self, k, type(getattr(self, k))(v))
        if self.lower_threshold > self.upper_threshold:
            self.lower_threshold, self.upper_threshold = self.upper_threshold, self.lower_threshold


settings = Settings()
