"""Shared data structures used across the pipeline."""
from __future__ import annotations

import threading
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Optional


@dataclass
class Document:
    """A piece of context: a vector-DB chunk or a web search result."""
    id: str
    text: str
    source: str                      # filename or URL
    origin: str = "local"            # "local" | "web"
    title: str = ""
    similarity: float = 0.0          # vector similarity (local) or search-engine score (web)
    relevance: Optional[float] = None  # score from the retrieval evaluator (0..1)
    label: str = ""                  # "correct" | "ambiguous" | "incorrect"
    reason: str = ""                 # evaluator explanation
    metadata: dict = field(default_factory=dict)

    def to_dict(self, max_chars: int | None = None) -> dict:
        d = asdict(self)
        if max_chars and len(d["text"]) > max_chars:
            d["text"] = d["text"][:max_chars].rstrip() + " …"
        return d


class Trace:
    """Collects per-request counters (LLM calls, tokens) in a thread-safe way."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.llm_calls = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.retrieval_attempts = 0
        self.web_searches = 0
        self.started = time.perf_counter()

    def add_llm(self, prompt_tokens: int, completion_tokens: int) -> None:
        with self._lock:
            self.llm_calls += 1
            self.prompt_tokens += prompt_tokens or 0
            self.completion_tokens += completion_tokens or 0

    def elapsed_ms(self) -> float:
        return round((time.perf_counter() - self.started) * 1000, 1)

    def summary(self) -> dict[str, Any]:
        return {
            "latency_ms": self.elapsed_ms(),
            "llm_calls": self.llm_calls,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.prompt_tokens + self.completion_tokens,
            "retrieval_attempts": self.retrieval_attempts,
            "web_searches": self.web_searches,
        }
