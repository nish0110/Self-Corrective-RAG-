"""Fallback web search: Tavily (recommended) or DuckDuckGo (no key needed)."""
from __future__ import annotations

import hashlib
import logging
from typing import Callable, Optional

import httpx

from .config import settings
from .models import Document

log = logging.getLogger("crag.web")

# Tests can replace this with a fake search function.
_override: Optional[Callable[[str, int], list[Document]]] = None


def set_search_override(fn: Optional[Callable[[str, int], list[Document]]]) -> None:
    global _override
    _override = fn


def _doc(i: int, url: str, title: str, content: str, score: float) -> Document:
    return Document(
        id="web-" + hashlib.sha1(url.encode()).hexdigest()[:10],
        text=content.strip(), source=url, origin="web", title=title or url,
        similarity=round(float(score or 0), 4), metadata={"rank": i},
    )


def tavily_search(query: str, n: int) -> list[Document]:
    if not settings.tavily_api_key:
        raise RuntimeError("TAVILY_API_KEY is not set")
    r = httpx.post(
        "https://api.tavily.com/search",
        headers={"Authorization": f"Bearer {settings.tavily_api_key}"},
        json={"query": query, "max_results": n, "search_depth": "advanced",
              "include_answer": False, "include_raw_content": False},
        timeout=settings.web_timeout,
    )
    r.raise_for_status()
    return [_doc(i, x.get("url", ""), x.get("title", ""), x.get("content", ""), x.get("score", 0))
            for i, x in enumerate(r.json().get("results", []))]


def duckduckgo_search(query: str, n: int) -> list[Document]:
    try:
        from ddgs import DDGS  # new package name
    except ImportError:
        from duckduckgo_search import DDGS  # older package name
    with DDGS() as ddg:
        rows = list(ddg.text(query, max_results=n))
    return [_doc(i, x.get("href", ""), x.get("title", ""), x.get("body", ""), 1 - i / (n + 1))
            for i, x in enumerate(rows)]


def available() -> bool:
    return _override is not None or settings.web_search_provider in ("tavily", "duckduckgo")


def search(query: str, n: Optional[int] = None) -> tuple[list[Document], str]:
    """Returns (documents, provider_used). Never raises; returns [] on failure."""
    n = n or settings.web_results
    if _override is not None:
        return _override(query, n), "override"
    provider = settings.web_search_provider
    if provider == "none":
        return [], "none"
    chain = ["tavily", "duckduckgo"] if provider == "tavily" else ["duckduckgo"]
    for p in chain:
        try:
            docs = tavily_search(query, n) if p == "tavily" else duckduckgo_search(query, n)
            docs = [d for d in docs if d.text]
            if docs:
                return docs, p
        except Exception as e:
            log.warning("web search via %s failed: %s", p, e)
    return [], "failed"
