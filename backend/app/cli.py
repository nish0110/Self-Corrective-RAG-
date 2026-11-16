"""Command-line interface.

    python -m app.cli ingest                # load the sample knowledge base
    python -m app.cli ingest path/to/folder # ingest your own files
    python -m app.cli ask "your question"   # run CRAG and print every step
    python -m app.cli ask "question" --baseline
    python -m app.cli eval [--limit N] [--category local]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .config import BACKEND_DIR


def _print_event(ev: dict) -> None:
    if ev["type"] == "step":
        print(f"  ▸ {ev['title']:<38} {ev['ms']:>8.0f} ms  {ev['summary']}")
        if ev["node"] == "evaluate":
            for d in ev["data"]["docs"]:
                print(f"      {d['relevance']:.2f} {d['label']:<10} {d['source']}  — {d['reason'][:70]}")
    elif ev["type"] == "result":
        print("\n" + "=" * 80)
        print(f"ROUTE: {ev['route']}   ACTION: {ev.get('action')}   CONFIDENCE: {ev.get('confidence')}")
        print("=" * 80)
        print(ev["answer"])
        print("\nSources:")
        for s in ev["sources"]:
            print(f"  [{s['n']}] ({s['origin']}) {s['title'] or s['source']}  {s['source'] if s['origin'] == 'web' else ''}")
        print("\nMetrics:", json.dumps(ev["metrics"]))


def main() -> None:
    ap = argparse.ArgumentParser(prog="crag")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("ingest")
    p.add_argument("folder", nargs="?", default=str(BACKEND_DIR / "data" / "sample_docs"))
    p.add_argument("--reset", action="store_true")
    p = sub.add_parser("ask")
    p.add_argument("question")
    p.add_argument("--baseline", action="store_true")
    p = sub.add_parser("eval")
    p.add_argument("--limit", type=int)
    p.add_argument("--category")
    p.add_argument("--delay", type=float, default=0.0, help="seconds between queries (rate limits)")
    a = ap.parse_args()

    if a.cmd == "ingest":
        from .ingest import ingest_directory
        from .vectorstore import get_store

        store = get_store()
        if a.reset:
            store.reset()
        for r in ingest_directory(store, Path(a.folder)):
            print(f"  {r['source']:<45} {r['chunks']} chunks")
        print(f"Total chunks in store: {store.count()}")
    elif a.cmd == "ask":
        from .pipeline import baseline_stream, crag_stream

        print(f"\nQ: {a.question}\n")
        for ev in (baseline_stream if a.baseline else crag_stream)(a.question):
            _print_event(ev)
    elif a.cmd == "eval":
        from . import evaluation

        items = evaluation.load_testset()
        if a.category:
            items = [i for i in items if i["category"] == a.category]
        if a.limit:
            items = items[: a.limit]
        rep = evaluation.run_evaluation(
            items, progress=lambda d, t, c: print(f"  [{d}/{t}] {c}"), delay=a.delay)
        print("\n" + evaluation.to_markdown(rep))
        print(f"Saved to {evaluation.RESULTS_DIR}")


if __name__ == "__main__":
    main()
