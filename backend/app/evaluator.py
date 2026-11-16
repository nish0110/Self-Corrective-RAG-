"""Retrieval evaluator — the heart of CRAG.

Scores every retrieved document for relevance to the query (0..1), labels each one,
and turns the scores into one of three *actions* (Yan et al., 2024):

    CORRECT    at least one document scores >= upper threshold
    INCORRECT  every document scores <  lower threshold
    AMBIGUOUS  anything in between

Three interchangeable backends:
    llm            LLM-as-judge with a rubric (default, most accurate)
    cross_encoder  ms-marco MiniLM cross-encoder (local, fast, no API cost) -- closest to
                   the fine-tuned T5 evaluator used in the original CRAG paper
    embedding      cosine similarity, rescaled (cheapest, weakest)
"""
from __future__ import annotations

import logging
import math
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from .config import settings
from .embeddings import cosine, get_embedder
from .llm import get_llm, today
from .models import Document, Trace
from . import prompts

log = logging.getLogger("crag.evaluator")

CORRECT, AMBIGUOUS, INCORRECT = "CORRECT", "AMBIGUOUS", "INCORRECT"

_cross_encoder = None


def _label(score: float) -> str:
    if score >= settings.upper_threshold:
        return "correct"
    if score < settings.lower_threshold:
        return "incorrect"
    return "ambiguous"


def _score_llm(query: str, doc: Document, time_sensitive: bool, trace: Optional[Trace]) -> tuple[float, str]:
    llm = get_llm()
    out = llm.chat_json(
        prompts.GRADER_SYSTEM.format(today=today()),
        prompts.GRADER_USER.format(question=query, document=doc.text[:3000]),
        task="grade",
        payload={"question": query, "document": doc.text, "time_sensitive": time_sensitive,
                 "origin": doc.origin},
        trace=trace,
    )
    try:
        score = float(out.get("score", 0))
    except (TypeError, ValueError):
        score = 0.0
    return max(0.0, min(1.0, score)), str(out.get("reason", ""))[:300]


def _score_cross_encoder(query: str, docs: list[Document]) -> list[tuple[float, str]]:
    global _cross_encoder
    if _cross_encoder is None:
        from sentence_transformers import CrossEncoder

        _cross_encoder = CrossEncoder(settings.cross_encoder_model)
    logits = _cross_encoder.predict([(query, d.text) for d in docs])
    return [(round(1 / (1 + math.exp(-float(x))), 3), f"cross-encoder logit {float(x):.2f}") for x in logits]


def _score_embedding(query: str, docs: list[Document]) -> list[tuple[float, str]]:
    emb = get_embedder()
    q = emb.embed_query(query)
    out = []
    for d, v in zip(docs, emb.embed_documents([d.text for d in docs])):
        sim = cosine(q, v)
        # MiniLM cosine of ~0.25 is weak, ~0.65 is strong: stretch that range to 0..1
        score = max(0.0, min(1.0, (sim - 0.2) / 0.5))
        out.append((round(score, 3), f"cosine similarity {sim:.2f}"))
    return out


def score_documents(query: str, docs: list[Document], *, time_sensitive: bool = False,
                    trace: Optional[Trace] = None) -> list[Document]:
    """Fill in `relevance`, `label`, `reason` on every document (in place) and return them."""
    if not docs:
        return docs
    backend = settings.evaluator_backend
    try:
        if backend == "cross_encoder":
            results = _score_cross_encoder(query, docs)
        elif backend == "embedding":
            results = _score_embedding(query, docs)
        else:
            with ThreadPoolExecutor(max_workers=settings.llm_max_workers) as ex:
                results = list(ex.map(lambda d: _score_llm(query, d, time_sensitive, trace), docs))
    except Exception as e:
        log.warning("evaluator backend %s failed (%s); falling back to embedding scores", backend, e)
        results = [(sc, f"[{backend} evaluator failed: {str(e)[:120]} — used {r}]")
                   for sc, r in _score_embedding(query, docs)]

    for d, (score, reason) in zip(docs, results):
        d.relevance = round(score, 3)
        d.label = _label(score)
        d.reason = reason
    return docs


def decide_action(docs: list[Document]) -> str:
    """CRAG action trigger based on the evaluator scores."""
    if not docs:
        return INCORRECT
    scores = [d.relevance or 0.0 for d in docs]
    if max(scores) >= settings.upper_threshold:
        return CORRECT
    if max(scores) < settings.lower_threshold:
        return INCORRECT
    return AMBIGUOUS
