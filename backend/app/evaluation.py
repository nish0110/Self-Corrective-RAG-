"""Evaluation harness: Traditional RAG vs CRAG on five query categories.

Metrics (as listed in the project methodology):
  Retrieval : context precision, recall, MRR, top-k accuracy (queries with gold sources)
  Generation: faithfulness, answer relevance, context relevance, hallucination rate,
              key-fact correctness
  System    : latency, retrieval attempts, web-search usage, tokens, LLM calls
  Routing   : routing accuracy (did CRAG take the path the category calls for?)
"""
from __future__ import annotations

import csv
import json
import logging
import statistics as st
import time
from pathlib import Path
from typing import Callable, Optional

from .config import BACKEND_DIR
from .evaluator import score_documents
from .generator import validate
from .llm import get_llm
from .models import Document
from .pipeline import run_baseline, run_crag
from . import prompts

log = logging.getLogger("crag.eval")

EVAL_DIR = BACKEND_DIR / "evaluation"
TESTSET = EVAL_DIR / "testset.json"
RESULTS_DIR = EVAL_DIR / "results"

CATEGORIES = ["local", "missing", "ambiguous", "time_sensitive", "distractor"]


def load_testset(path: Path = TESTSET) -> list[dict]:
    return json.loads(path.read_text())


def _judge(system: str, user: str, task: str, payload: dict) -> float:
    out = get_llm().chat_json(system, user, task=task, payload=payload)
    try:
        return max(0.0, min(1.0, float(out.get("score", 0))))
    except (TypeError, ValueError):
        return 0.0


def _retrieval_metrics(ranked_sources: list[str], context_sources: list[str], gold: list[str]) -> dict:
    gold_set = set(gold)
    mrr = 0.0
    for i, s in enumerate(ranked_sources, 1):
        if s in gold_set:
            mrr = 1 / i
            break
    prec = (sum(1 for s in context_sources if s in gold_set) / len(context_sources)) if context_sources else 0.0
    rec = len(gold_set & set(context_sources)) / len(gold_set)
    return {"precision": round(prec, 3), "recall": round(rec, 3), "mrr": round(mrr, 3),
            "topk_hit": 1.0 if gold_set & set(ranked_sources) else 0.0}


def _routing_correct(item: dict, res: dict) -> bool:
    cat = item["category"]
    route = res.get("route")
    ctx_sources = {s["source"] for s in res.get("sources", [])}
    if cat == "local":
        return route == "local"
    if cat == "ambiguous":
        return bool(set(item.get("gold_sources", [])) & ctx_sources) or route in ("web", "hybrid")
    # missing / time_sensitive / distractor -> web search must be involved
    return route in ("web", "hybrid") or bool(res.get("metrics", {}).get("web_searches"))


def evaluate_one(item: dict, system: str) -> dict:
    q = item["question"]
    t0 = time.perf_counter()
    res = run_crag(q) if system == "crag" else run_baseline(q)
    latency = (time.perf_counter() - t0) * 1000
    sources = res.get("sources", [])
    ctx_docs = [Document(id=str(s["n"]), text=s["text"], source=s["source"], origin=s["origin"])
                for s in sources]

    # Faithfulness (re-use CRAG's own validation if it ran on this exact context).
    v = res.get("validation") if system == "crag" else None
    if not v:
        v = validate(q, ctx_docs, res["answer"])

    # Context relevance: mean evaluator score of the context the generator actually saw.
    if system == "crag":
        ctx_rel = [s.get("relevance") for s in sources]
        missing = [d for d, r in zip(ctx_docs, ctx_rel) if r is None]  # web docs are not pre-graded
        if missing:
            score_documents(q, missing)
            it = iter(d.relevance for d in missing)
            ctx_rel = [r if r is not None else next(it) for r in ctx_rel]
    else:
        score_documents(q, ctx_docs)
        ctx_rel = [d.relevance for d in ctx_docs]
    context_relevance = st.mean(ctx_rel) if ctx_rel else 0.0

    answer_rel = _judge(prompts.JUDGE_RELEVANCE_SYSTEM,
                        f"QUESTION: {q}\nANSWER: {res['answer']}", "judge_relevance",
                        {"question": q, "answer": res["answer"]})
    facts = item.get("key_facts", [])
    correctness = _judge(prompts.JUDGE_CORRECTNESS_SYSTEM,
                         f"QUESTION: {q}\nKEY FACTS: {json.dumps(facts)}\nANSWER: {res['answer']}",
                         "judge_correctness", {"facts": facts, "answer": res["answer"]}) if facts else None

    row = {
        "id": item["id"], "category": item["category"], "system": system, "question": q,
        "answer": res["answer"], "route": res.get("route"), "action": res.get("action"),
        "faithful": 1.0 if v.get("grounded") else 0.0,
        "validation_score": v.get("score"),
        "answer_relevance": round(answer_rel, 3),
        "context_relevance": round(context_relevance, 3),
        "correctness": correctness,
        "latency_ms": round(latency, 1),
        "llm_calls": res["metrics"]["llm_calls"],
        "tokens": res["metrics"]["total_tokens"],
        "retrieval_attempts": res["metrics"]["retrieval_attempts"],
        "web_search": 1.0 if res["metrics"]["web_searches"] else 0.0,
        "routing_correct": (1.0 if _routing_correct(item, res) else 0.0) if system == "crag" else None,
    }
    gold = item.get("gold_sources") or []
    if gold:
        if system == "crag":
            first = res.get("attempts", [{}])[-1].get("docs", [])
            ranked = [d["source"] for d in sorted(first, key=lambda d: -(d.get("relevance") or 0))]
        else:
            ranked = [s["source"] for s in sources]
        ctx_local = [s["source"] for s in sources if s["origin"] == "local"]
        row.update(_retrieval_metrics(ranked, ctx_local, gold))
    return row


def _mean(rows: list[dict], key: str) -> Optional[float]:
    vals = [r[key] for r in rows if r.get(key) is not None]
    return round(st.mean(vals), 3) if vals else None


METRIC_KEYS = ["precision", "recall", "mrr", "topk_hit", "faithful", "answer_relevance",
               "context_relevance", "correctness", "latency_ms", "llm_calls", "tokens",
               "retrieval_attempts", "web_search", "routing_correct"]


def summarise(rows: list[dict]) -> dict:
    summary: dict = {"overall": {}, "by_category": {}}
    for system in ("baseline", "crag"):
        rs = [r for r in rows if r["system"] == system]
        m = {k: _mean(rs, k) for k in METRIC_KEYS}
        m["hallucination_rate"] = round(1 - m["faithful"], 3) if m["faithful"] is not None else None
        summary["overall"][system] = m
        for cat in CATEGORIES:
            rc = [r for r in rs if r["category"] == cat]
            if rc:
                summary["by_category"].setdefault(cat, {})[system] = {
                    k: _mean(rc, k) for k in ("correctness", "faithful", "context_relevance",
                                              "web_search", "routing_correct", "latency_ms")}
    return summary


def run_evaluation(items: Optional[list[dict]] = None, progress: Optional[Callable[[int, int, str], None]] = None,
                   delay: float = 0.0, save: bool = True) -> dict:
    items = items if items is not None else load_testset()
    rows = []
    total = len(items) * 2
    done = 0
    for item in items:
        for system in ("baseline", "crag"):
            try:
                rows.append(evaluate_one(item, system))
            except Exception as e:  # keep going; record the failure
                log.exception("eval failed for %s/%s", item["id"], system)
                rows.append({"id": item["id"], "category": item["category"], "system": system,
                             "question": item["question"], "answer": f"ERROR: {e}"})
            done += 1
            if progress:
                progress(done, total, f"{item['id']} ({system})")
            if delay:
                time.sleep(delay)
    report = {"created_at": time.strftime("%Y-%m-%d %H:%M:%S"), "n_questions": len(items),
              "llm": f"{get_llm().provider}:{get_llm().model}",
              "summary": summarise([r for r in rows if "faithful" in r]), "rows": rows}
    if save:
        save_report(report)
    return report


def save_report(report: dict) -> Path:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    (RESULTS_DIR / "latest.json").write_text(json.dumps(report, indent=2))
    rows = report["rows"]
    keys = ["id", "category", "system", "route", "action", *METRIC_KEYS, "question", "answer"]
    with open(RESULTS_DIR / "latest.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    (RESULTS_DIR / "latest.md").write_text(to_markdown(report))
    try:
        make_charts(report, RESULTS_DIR)
    except Exception as e:  # matplotlib optional
        log.info("charts skipped: %s", e)
    return RESULTS_DIR


def to_markdown(report: dict) -> str:
    o = report["summary"]["overall"]
    b, c = o.get("baseline", {}), o.get("crag", {})
    nice = {
        "precision": "Context precision", "recall": "Context recall", "mrr": "MRR",
        "topk_hit": "Top-k accuracy", "faithful": "Faithfulness", "hallucination_rate": "Hallucination rate ↓",
        "answer_relevance": "Answer relevance", "context_relevance": "Context relevance",
        "correctness": "Key-fact correctness", "routing_correct": "Routing accuracy",
        "web_search": "Web-search usage", "retrieval_attempts": "Retrieval attempts",
        "llm_calls": "LLM calls", "tokens": "Tokens", "latency_ms": "Latency (ms) ↓",
    }
    lines = [f"# CRAG vs Traditional RAG — evaluation report",
             f"", f"- Date: {report['created_at']}", f"- Questions: {report['n_questions']}",
             f"- LLM: `{report['llm']}`", "", "## Overall", "",
             "| Metric | Traditional RAG | CRAG |", "|---|---|---|"]
    for k, label in nice.items():
        lines.append(f"| {label} | {b.get(k, '—') if b.get(k) is not None else '—'} | "
                     f"{c.get(k, '—') if c.get(k) is not None else '—'} |")
    lines += ["", "## By query category (key-fact correctness)", "",
              "| Category | Traditional RAG | CRAG | CRAG web usage | CRAG routing acc. |", "|---|---|---|---|---|"]
    for cat, v in report["summary"]["by_category"].items():
        bb, cc = v.get("baseline", {}), v.get("crag", {})
        lines.append(f"| {cat} | {bb.get('correctness')} | {cc.get('correctness')} | "
                     f"{cc.get('web_search')} | {cc.get('routing_correct')} |")
    return "\n".join(lines) + "\n"


def make_charts(report: dict, out: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    o = report["summary"]["overall"]
    keys = ["context_relevance", "faithful", "answer_relevance", "correctness"]
    labels = ["Context\nrelevance", "Faithfulness", "Answer\nrelevance", "Correctness"]
    b = [o["baseline"].get(k) or 0 for k in keys]
    c = [o["crag"].get(k) or 0 for k in keys]
    fig, ax = plt.subplots(figsize=(7, 3.6))
    x = range(len(keys))
    ax.bar([i - 0.2 for i in x], b, 0.4, label="Traditional RAG", color="#9aa4b2")
    ax.bar([i + 0.2 for i in x], c, 0.4, label="CRAG", color="#2563eb")
    ax.set_xticks(list(x), labels)
    ax.set_ylim(0, 1)
    ax.legend(frameon=False)
    ax.spines[["top", "right"]].set_visible(False)
    ax.set_title("Quality metrics (higher is better)")
    fig.tight_layout()
    fig.savefig(out / "quality.png", dpi=160)
    plt.close(fig)

    cats = list(report["summary"]["by_category"].keys())
    bb = [report["summary"]["by_category"][k].get("baseline", {}).get("correctness") or 0 for k in cats]
    cc = [report["summary"]["by_category"][k].get("crag", {}).get("correctness") or 0 for k in cats]
    fig, ax = plt.subplots(figsize=(7, 3.6))
    x = range(len(cats))
    ax.bar([i - 0.2 for i in x], bb, 0.4, label="Traditional RAG", color="#9aa4b2")
    ax.bar([i + 0.2 for i in x], cc, 0.4, label="CRAG", color="#2563eb")
    ax.set_xticks(list(x), [k.replace("_", "\n") for k in cats])
    ax.set_ylim(0, 1)
    ax.legend(frameon=False)
    ax.spines[["top", "right"]].set_visible(False)
    ax.set_title("Key-fact correctness by query category")
    fig.tight_layout()
    fig.savefig(out / "by_category.png", dpi=160)
    plt.close(fig)
