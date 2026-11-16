"""The Corrective RAG pipeline (and the plain-RAG baseline used for comparison).

                         ┌──────────────┐
  question ─► retrieve ─►│  evaluator   │─► action
                         └──────────────┘
   CORRECT   ─► refine local docs ───────────────────────────────► generate ─► validate
   AMBIGUOUS ─► keep partly-relevant local docs + rewrite ─► web ─► generate ─► validate
   INCORRECT ─► rewrite ─► re-retrieve (up to MAX_REWRITES) ─► still bad? discard local,
                rewrite for web ─► web search ─► generate ─► validate
   validate fails ─► self-correct: escalate to web search (if not used yet) or
                     regenerate with a stricter prompt (up to MAX_VALIDATION_RETRIES)

`crag_stream()` is a generator of events so the UI can animate each step live.
"""
from __future__ import annotations

import logging
import time
from typing import Iterator

from .config import settings
from .evaluator import AMBIGUOUS, CORRECT, INCORRECT, decide_action, score_documents
from .generator import generate, validate
from .models import Document, Trace
from .refiner import refine
from .rewriter import rewrite
from .textutils import is_time_sensitive
from .vectorstore import get_store
from . import websearch

log = logging.getLogger("crag.pipeline")

ROUTE_INFO = {
    CORRECT: ("local", "Relevant local context found → answer from the knowledge base."),
    AMBIGUOUS: ("hybrid", "Context is only partly relevant → combine local docs with web search."),
    INCORRECT: ("web", "Local context is irrelevant → discard it, rewrite the query and search the web."),
}


def _docs(docs: list[Document], n: int = 700) -> list[dict]:
    return [d.to_dict(max_chars=n) for d in docs]


class _Step:
    """Helper that times a step and builds its event."""

    def __init__(self, node: str, title: str) -> None:
        self.node, self.title, self.t0 = node, title, time.perf_counter()

    def done(self, summary: str, **data) -> dict:
        return {"type": "step", "node": self.node, "title": self.title, "summary": summary,
                "ms": round((time.perf_counter() - self.t0) * 1000, 1), "data": data}


def _start(node: str, title: str) -> dict:
    return {"type": "start", "node": node, "title": title}


def crag_stream(question: str) -> Iterator[dict]:
    trace = Trace()
    store = get_store()
    q = " ".join(question.split())
    ts = is_time_sensitive(q)
    path: list[str] = []

    # 1. Query processing --------------------------------------------------
    s = _Step("query", "Query processing")
    path.append("query")
    yield s.done("Time-sensitive question: will distrust possibly outdated local docs." if ts
                 else "Question normalised.", query=q, time_sensitive=ts)

    # 2-4. Retrieve → evaluate → route (with rewrite loop on INCORRECT) ------
    current_q, tried, attempt = q, [q], 0
    rewrites: list[dict] = []
    attempts: list[dict] = []
    while True:
        attempt += 1
        yield _start("retrieve", "Vector search")
        s = _Step("retrieve", f"Vector search (attempt {attempt})")
        docs = store.search(current_q, settings.top_k)
        trace.retrieval_attempts += 1
        path.append("retrieve")
        yield s.done(f"Retrieved {len(docs)} chunks from ChromaDB" + ("" if docs else " — knowledge base is empty"),
                     query=current_q, attempt=attempt, docs=_docs(docs, 400))

        yield _start("evaluate", "Relevance evaluation")
        s = _Step("evaluate", "Relevance evaluation")
        # Always grade against the user's ORIGINAL question, not the rewrite.
        score_documents(q, docs, time_sensitive=ts, trace=trace)
        action = decide_action(docs)
        path.append("evaluate")
        best = max((d.relevance or 0 for d in docs), default=0)
        yield s.done(f"Best relevance {best:.2f} (thresholds: upper {settings.upper_threshold}, "
                     f"lower {settings.lower_threshold}) via {settings.evaluator_backend} evaluator",
                     docs=_docs(docs, 400), action=action, best=best,
                     upper=settings.upper_threshold, lower=settings.lower_threshold,
                     backend=settings.evaluator_backend)
        attempts.append({"query": current_q, "action": action, "best": best,
                         "docs": _docs(docs, 400)})

        s = _Step("route", "Routing decision")
        path.append("route")
        can_retry = action == INCORRECT and attempt <= settings.max_rewrites and store.count() > 0
        route, why = ROUTE_INFO[action]
        yield s.done(f"{action} → " + ("rewrite the query and retry the vector search" if can_retry else why),
                     action=action, route=route, retry=can_retry)
        if not can_retry:
            break

        yield _start("rewrite", "Query rewrite")
        s = _Step("rewrite", "Query rewrite (for re-retrieval)")
        new_q = rewrite(q, "retrieval", previous=tried[1:], trace=trace)
        tried.append(new_q)
        rewrites.append({"purpose": "retrieval", "query": new_q})
        path.append("rewrite")
        yield s.done(f"“{current_q}” → “{new_q}”", original=current_q, rewritten=new_q, purpose="retrieval")
        current_q = new_q

    # 5. Knowledge selection ----------------------------------------------
    if action == CORRECT:
        local_kept = [d for d in docs if d.label == "correct"]
    elif action == AMBIGUOUS:
        local_kept = [d for d in docs if d.label != "incorrect"]
    else:
        local_kept = []
    need_web = action in (AMBIGUOUS, INCORRECT)
    web_docs: list[Document] = []
    web_used = False
    web_provider = None

    def do_web_search() -> Iterator[dict]:
        nonlocal web_docs, web_used, web_provider
        yield _start("rewrite", "Query rewrite")
        s = _Step("rewrite", "Query rewrite (for web search)")
        wq = rewrite(q, "web", trace=trace)
        rewrites.append({"purpose": "web", "query": wq})
        path.append("rewrite")
        yield s.done(f"Web query: “{wq}”", original=q, rewritten=wq, purpose="web")

        yield _start("web_search", "Web search")
        s = _Step("web_search", "Web search")
        if websearch.available():
            web_docs, web_provider = websearch.search(wq)
        else:
            web_docs, web_provider = [], "disabled"
        trace.web_searches += 1
        web_used = True
        path.append("web_search")
        msg = (f"{len(web_docs)} results from {web_provider}" if web_docs
               else f"No web results (provider: {web_provider}).")
        yield s.done(msg, query=wq, provider=web_provider, docs=_docs(web_docs, 500))

    if need_web:
        yield from do_web_search()

    # 6. Knowledge refinement ---------------------------------------------
    def build_context() -> Iterator[dict]:
        nonlocal context
        yield _start("refine", "Knowledge refinement")
        s = _Step("refine", "Knowledge refinement")
        refined_local, st1 = refine(q, local_kept)
        refined_web, st2 = refine(q, web_docs)
        context = refined_local + refined_web
        path.append("refine")
        red = (st1.get("chars_before", 0) + st2.get("chars_before", 0))
        aft = (st1.get("chars_after", 0) + st2.get("chars_after", 0))
        yield s.done(
            f"{len(refined_local)} local + {len(refined_web)} web passages"
            + (f"; noise removed: {round(100 * (1 - aft / red))}% of text" if red else ""),
            local=len(refined_local), web=len(refined_web), enabled=settings.enable_refinement,
            chars_before=red, chars_after=aft)

    context: list[Document] = []
    yield from build_context()

    # 7. Generation + 8. validation / self-correction ----------------------
    validation = None
    strict = False
    corrections: list[str] = []
    for round_ in range(settings.max_validation_retries + 1):
        yield _start("generate", "Answer generation")
        s = _Step("generate", "Answer generation" + (" (retry)" if round_ else ""))
        answer = generate(q, context, strict=strict, trace=trace)
        path.append("generate")
        yield s.done(f"Generated {len(answer.split())} words from {len(context)} passages", answer=answer)

        if not settings.enable_validation:
            break
        yield _start("validate", "Answer validation")
        s = _Step("validate", "Answer validation")
        validation = validate(q, context, answer, trace=trace)
        ok = validation.get("skipped") or (validation["grounded"] and validation["answers_question"]
              and validation["score"] >= settings.validation_threshold)
        if validation.get("skipped"):
            validation = None
        path.append("validate")
        if validation is None:
            yield s.done("Skipped (validator unavailable)", passed=True)
            break
        yield s.done(("PASS" if ok else "FAIL") + f" — score {validation['score']:.2f}"
                     + (f" ({validation['issues']})" if validation["issues"] and not ok else ""),
                     **validation, passed=ok)
        if ok or round_ == settings.max_validation_retries:
            break

        # Self-correction
        s = _Step("correct", "Self-correction")
        if not web_used and websearch.available():
            path.append("correct")
            corrections.append("escalated to web search")
            yield s.done("Answer not well supported → escalating to web search for more evidence.",
                         strategy="web_escalation")
            yield from do_web_search()
            yield from build_context()
        elif context and not validation["grounded"]:
            path.append("correct")
            strict = True
            corrections.append("regenerated with strict grounding")
            yield s.done("Answer contained unsupported claims → regenerating with a stricter prompt.",
                         strategy="strict_regeneration")
        else:
            # Nothing more to try: keep the honest "insufficient information" answer.
            break

    # 9. Final -------------------------------------------------------------
    sources_local = sum(1 for d in context if d.origin == "local")
    sources_web = len(context) - sources_local
    route = "local" if sources_web == 0 else ("web" if sources_local == 0 else "hybrid")
    if not context:
        route = "none"
    confidence = validation["score"] if validation else max((d.relevance or 0 for d in docs), default=0)
    path.append("final")
    yield {
        "type": "result",
        "mode": "crag",
        "question": q,
        "answer": answer,
        "action": action,
        "route": route,
        "confidence": round(confidence, 3),
        "time_sensitive": ts,
        "sources": [{**d.to_dict(max_chars=600), "n": i} for i, d in enumerate(context, 1)],
        "attempts": attempts,
        "rewrites": rewrites,
        "web_provider": web_provider,
        "validation": validation,
        "corrections": corrections,
        "path": path,
        "metrics": trace.summary(),
    }


def run_crag(question: str, on_event=None) -> dict:
    result = None
    for ev in crag_stream(question):
        if on_event:
            on_event(ev)
        if ev["type"] == "result":
            result = ev
    return result


# ----------------------------------------------------------------- baseline
def baseline_stream(question: str) -> Iterator[dict]:
    """Traditional RAG: retrieve top-k → generate. No evaluation, no correction."""
    trace = Trace()
    q = " ".join(question.split())
    yield _start("retrieve", "Vector search")
    s = _Step("retrieve", "Vector search")
    docs = get_store().search(q, settings.top_k)
    trace.retrieval_attempts += 1
    yield s.done(f"Retrieved {len(docs)} chunks", query=q, docs=_docs(docs, 400))
    yield _start("generate", "Answer generation")
    s = _Step("generate", "Answer generation")
    answer = generate(q, docs, trace=trace)
    yield s.done("Generated answer from all retrieved chunks (unfiltered)", answer=answer)
    yield {
        "type": "result", "mode": "baseline", "question": q, "answer": answer,
        "action": None, "route": "local" if docs else "none", "confidence": None,
        "sources": [{**d.to_dict(max_chars=600), "n": i} for i, d in enumerate(docs, 1)],
        "path": ["retrieve", "generate", "final"], "metrics": trace.summary(),
    }


def run_baseline(question: str) -> dict:
    for ev in baseline_stream(question):
        if ev["type"] == "result":
            return ev
    return {}
