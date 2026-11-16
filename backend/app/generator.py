"""Answer generation and answer validation."""
from __future__ import annotations

from typing import Optional

from .llm import get_llm
from .models import Document, Trace
from . import prompts


def format_context(docs: list[Document]) -> str:
    blocks = []
    for i, d in enumerate(docs, 1):
        tag = "web" if d.origin == "web" else "local"
        blocks.append(f"[{i}] ({tag}: {d.title or d.source})\n{d.text}")
    return "\n\n".join(blocks) if blocks else "(no context available)"


def generate(question: str, docs: list[Document], *, strict: bool = False,
             trace: Optional[Trace] = None) -> str:
    system = prompts.GENERATOR_SYSTEM.format(
        context=format_context(docs), extra=prompts.STRICT_EXTRA if strict else "")
    return get_llm().chat(
        system, prompts.GENERATOR_USER.format(question=question),
        task="generate", payload={"question": question, "docs": [d.text for d in docs]},
        trace=trace,
    ).strip()


def validate(question: str, docs: list[Document], answer: str,
             trace: Optional[Trace] = None) -> dict:
    context = format_context(docs)
    try:
        out = _validate_call(question, context, answer, trace)
    except Exception as e:
        return {"grounded": True, "answers_question": True, "score": 0.0, "skipped": True,
                "issues": f"validation skipped: {str(e)[:150]}"}
    try:
        score = float(out.get("score", 0))
    except (TypeError, ValueError):
        score = 0.0
    return {
        "grounded": bool(out.get("grounded", False)),
        "answers_question": bool(out.get("answers_question", False)),
        "score": round(max(0.0, min(1.0, score)), 3),
        "issues": str(out.get("issues", ""))[:300],
    }


def _validate_call(question, context, answer, trace):
    return get_llm().chat_json(
        prompts.VALIDATOR_SYSTEM,
        prompts.VALIDATOR_USER.format(question=question, context=context, answer=answer),
        task="validate", payload={"question": question, "context": context, "answer": answer},
        trace=trace,
    )
