"""Knowledge refinement ("decompose-then-recompose" from the CRAG paper).

Each relevant document is split into small "knowledge strips" (1-2 sentences), each
strip is scored against the query, irrelevant strips are dropped and the remaining
ones are re-joined in their original order. This removes noise before generation.
"""
from __future__ import annotations

from dataclasses import replace

from .config import settings
from .embeddings import cosine, get_embedder
from .models import Document
from . import textutils as tu


def _strips(text: str, window: int = 1) -> list[str]:
    sents = tu.split_sentences(text)
    if len(sents) <= window:
        return [" ".join(sents)] if sents else []
    return [" ".join(sents[i:i + window]) for i in range(0, len(sents), window)]


def refine(query: str, docs: list[Document], max_strips_per_doc: int = 6) -> tuple[list[Document], dict]:
    if not settings.enable_refinement or not docs:
        return docs, {"enabled": False}
    emb = get_embedder()
    q = emb.embed_query(query)
    refined, before, after = [], 0, 0
    for d in docs:
        strips = _strips(d.text)
        if not strips:
            continue
        vecs = emb.embed_documents(strips)
        scored = [(0.7 * cosine(q, v) + 0.3 * tu.coverage(query, s), i, s)
                  for i, (s, v) in enumerate(zip(strips, vecs))]
        keep = [x for x in scored if x[0] >= settings.strip_threshold]
        if not keep:  # keep the best strip so that a relevant document never disappears
            keep = sorted(scored, key=lambda x: -x[0])[:1]
        keep = sorted(sorted(keep, key=lambda x: -x[0])[:max_strips_per_doc], key=lambda x: x[1])
        text = "\n".join(s for _, _, s in keep)
        before += len(d.text)
        after += len(text)
        refined.append(replace(d, text=text, metadata={**d.metadata, "strips_kept": len(keep),
                                                         "strips_total": len(strips)}))
    stats = {"enabled": True, "chars_before": before, "chars_after": after,
             "reduction": round(1 - after / before, 3) if before else 0.0}
    return refined, stats
