"""Query rewriting: one flavour for vector re-retrieval, one for web search."""
from __future__ import annotations

from typing import Optional

from .llm import get_llm, today
from .models import Trace
from . import prompts


def rewrite(question: str, mode: str = "retrieval", previous: Optional[list[str]] = None,
            trace: Optional[Trace] = None) -> str:
    """mode: "retrieval" (clarify for vector search) or "web" (keyword search query)."""
    system = (prompts.REWRITE_WEB_SYSTEM.format(today=today()) if mode == "web"
              else prompts.REWRITE_RETRIEVAL_SYSTEM)
    prev = ""
    if previous:
        prev = "\nThese earlier rewrites did not retrieve good documents, try a different angle:\n- " + \
               "\n- ".join(previous)
    try:
        out = get_llm().chat_json(
            system, prompts.REWRITE_USER.format(question=question, previous=prev),
            task="rewrite", payload={"question": question, "mode": mode}, trace=trace,
        )
    except Exception:  # rewriting is an optimisation: fall back to the original question
        return question
    q = str(out.get("query", "")).strip().strip('"')
    return q or question
