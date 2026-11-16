"""FastAPI application: REST + streaming API for the CRAG system."""
from __future__ import annotations

import json
import logging
import threading
import time
from pathlib import Path
from typing import Literal, Optional

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.requests import Request
from fastapi.responses import JSONResponse
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .config import BACKEND_DIR, settings
from .ingest import SUPPORTED, ingest_directory, ingest_file
from .llm import get_llm
from .pipeline import baseline_stream, crag_stream, run_baseline, run_crag
from .vectorstore import get_store
from . import evaluation, websearch

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("crag.api")

SAMPLE_DIR = BACKEND_DIR / "data" / "sample_docs"
FRONTEND_DIST = BACKEND_DIR.parent / "frontend" / "dist"

app = FastAPI(title="Self-Corrective RAG (CRAG)", version="1.0.0",
              description="Corrective RAG with retrieval evaluation, routing, query rewriting, "
                          "web-search fallback and answer validation.")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.on_event("startup")
def warm_up():
    """Load the embedding model and open the database once, before any request arrives."""
    try:
        store = get_store()
        log.info("Ready: %s embeddings, %d chunks, LLM %s:%s", store.embedder.name, store.count(),
                 get_llm().provider, get_llm().model)
    except Exception:
        log.exception("startup warm-up failed (the System check page will show details)")


@app.exception_handler(Exception)
async def friendly_errors(request: Request, exc: Exception):
    log.exception("unhandled error on %s", request.url.path)
    return JSONResponse(status_code=500, content={"detail": f"{type(exc).__name__}: {exc}"})


class QueryIn(BaseModel):
    query: str = Field(..., min_length=2, max_length=2000)
    mode: Literal["crag", "baseline"] = "crag"


class ConfigIn(BaseModel):
    top_k: Optional[int] = Field(None, ge=1, le=20)
    upper_threshold: Optional[float] = Field(None, ge=0, le=1)
    lower_threshold: Optional[float] = Field(None, ge=0, le=1)
    max_rewrites: Optional[int] = Field(None, ge=0, le=5)
    enable_refinement: Optional[bool] = None
    strip_threshold: Optional[float] = Field(None, ge=0, le=1)
    web_search_provider: Optional[Literal["tavily", "duckduckgo", "none"]] = None
    web_results: Optional[int] = Field(None, ge=1, le=10)
    enable_validation: Optional[bool] = None
    max_validation_retries: Optional[int] = Field(None, ge=0, le=3)
    validation_threshold: Optional[float] = Field(None, ge=0, le=1)
    evaluator_backend: Optional[Literal["llm", "cross_encoder", "embedding"]] = None


# ------------------------------------------------------------------ health & config
@app.get("/api/health")
def health():
    store = get_store()
    llm = get_llm()
    return {
        "status": "ok",
        "llm": {"provider": llm.provider, "model": llm.model, "mock": llm.is_mock},
        "embeddings": store.embedder.name,
        "evaluator": settings.evaluator_backend,
        "web_search": settings.web_search_provider if websearch.available() else "none",
        "documents": len(store.list_sources()),
        "chunks": store.count(),
    }


@app.get("/api/config")
def get_config():
    return settings.public()


@app.put("/api/config")
def put_config(body: ConfigIn):
    settings.update(body.model_dump(exclude_none=True))
    return settings.public()


def _check(name: str, fn, hint: str) -> dict:
    t0 = time.perf_counter()
    try:
        detail = fn()
        return {"name": name, "ok": True, "detail": detail, "ms": round((time.perf_counter() - t0) * 1000)}
    except Exception as e:
        log.warning("diagnostic %s failed: %s", name, e)
        return {"name": name, "ok": False, "error": str(e)[:400], "hint": hint,
                "ms": round((time.perf_counter() - t0) * 1000)}


@app.get("/api/diagnostics")
def diagnostics():
    """Tests every component with a real call so problems are visible in the UI."""
    def llm():
        c = get_llm()
        if c.is_mock:
            return "Demo mode: offline heuristic LLM (set LLM_PROVIDER and LLM_API_KEY in backend/.env for real answers)"
        r = c.ping()
        return f"{c.provider} · {r['model']} responded"

    def emb():
        e = get_store().embedder
        v = e.embed_query("diagnostic test")
        warn = " (fallback — install sentence-transformers for good retrieval)" if e.name.startswith("hash") else ""
        return f"{e.name}, {len(v)} dimensions{warn}"

    def db():
        st = get_store()
        return f"ChromaDB OK · {len(st.list_sources())} documents · {st.count()} chunks"

    def web():
        if not websearch.available() or settings.web_search_provider == "none":
            raise RuntimeError("Web search is disabled (WEB_SEARCH_PROVIDER=none)")
        docs, provider = websearch.search("retrieval augmented generation", 2)
        if not docs:
            raise RuntimeError(f"No results from {settings.web_search_provider}")
        return f"{provider} returned {len(docs)} results"

    llm_hint = {
        "groq": "Get a free key at console.groq.com/keys and set LLM_API_KEY. Check the model list at console.groq.com/docs/models.",
        "gemini": "Get a free key at aistudio.google.com/apikey and set LLM_API_KEY.",
        "ollama": "Start Ollama (`ollama serve`) and pull a model (`ollama pull llama3.1`).",
    }.get(settings.llm_provider, "Check LLM_PROVIDER, LLM_API_KEY and LLM_MODEL in backend/.env.")
    checks = [
        _check("Language model", llm, llm_hint),
        _check("Embeddings", emb, "pip install sentence-transformers (needs internet once to download the model)."),
        _check("Vector database", db, "Delete backend/storage/ and restart if the database is corrupted."),
        _check("Web search", web, "Set TAVILY_API_KEY (free at tavily.com) or `pip install ddgs` for DuckDuckGo."),
    ]
    return {"ok": all(c["ok"] for c in checks[:3]), "checks": checks}


# ------------------------------------------------------------------ documents
@app.get("/api/documents")
def list_documents():
    return {"documents": get_store().list_sources(), "chunks": get_store().count()}


@app.post("/api/documents/upload")
async def upload(files: list[UploadFile] = File(...)):
    out = []
    for f in files:
        name = Path((f.filename or "upload.txt").replace("\\", "/")).name
        ext = Path(name).suffix.lower()
        if ext not in SUPPORTED:
            out.append({"source": name, "error": f"'{ext or 'no extension'}' files are not supported. "
                                                 f"Use: {', '.join(sorted(SUPPORTED))}"})
            continue
        try:
            data = await f.read()
            res = await run_in_threadpool(ingest_file, get_store(), name, data)
            out.append(res)
        except ValueError as e:
            out.append({"source": name, "error": str(e)})
        except Exception as e:
            log.exception("ingest failed")
            out.append({"source": name, "error": f"{type(e).__name__}: {e}"})
    return {"results": out}


@app.post("/api/documents/load-samples")
def load_samples():
    return {"results": ingest_directory(get_store(), SAMPLE_DIR)}


@app.delete("/api/documents/{source}")
def delete_document(source: str):
    n = get_store().delete_source(source)
    if not n:
        raise HTTPException(404, "document not found")
    return {"deleted_chunks": n}


@app.delete("/api/documents")
def reset_documents():
    get_store().reset()
    return {"ok": True}


# ------------------------------------------------------------------ querying
@app.post("/api/query")
def query(body: QueryIn):
    return run_crag(body.query) if body.mode == "crag" else run_baseline(body.query)


@app.post("/api/query/stream")
def query_stream(body: QueryIn):
    """Server-sent events: one `data:` line per pipeline step, then the final result."""
    gen = crag_stream if body.mode == "crag" else baseline_stream

    def events():
        try:
            for ev in gen(body.query):
                yield f"data: {json.dumps(ev, default=str)}\n\n"
        except Exception as e:
            log.exception("pipeline error")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(events(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.post("/api/compare")
def compare(body: QueryIn):
    return {"baseline": run_baseline(body.query), "crag": run_crag(body.query)}


# ------------------------------------------------------------------ evaluation
_eval_state = {"running": False, "done": 0, "total": 0, "current": "", "error": None}


@app.get("/api/eval/testset")
def eval_testset():
    return {"items": evaluation.load_testset()}


@app.post("/api/eval/run")
def eval_run(limit: Optional[int] = None, category: Optional[str] = None):
    if _eval_state["running"]:
        raise HTTPException(409, "evaluation already running")
    items = evaluation.load_testset()
    if category:
        items = [i for i in items if i["category"] == category]
    if limit:
        items = items[:limit]

    def progress(done, total, current):
        _eval_state.update(done=done, total=total, current=current)

    def work():
        try:
            evaluation.run_evaluation(items, progress=progress)
        except Exception as e:
            log.exception("evaluation failed")
            _eval_state["error"] = str(e)
        finally:
            _eval_state["running"] = False

    _eval_state.update(running=True, done=0, total=len(items) * 2, current="starting", error=None)
    threading.Thread(target=work, daemon=True).start()
    return _eval_state


@app.get("/api/eval/status")
def eval_status():
    return _eval_state


@app.get("/api/eval/results")
def eval_results():
    p = evaluation.RESULTS_DIR / "latest.json"
    if not p.exists():
        return {"available": False}
    return {"available": True, **json.loads(p.read_text())}


@app.get("/api/eval/chart/{name}")
def eval_chart(name: Literal["quality", "by_category"]):
    p = evaluation.RESULTS_DIR / f"{name}.png"
    if not p.exists():
        raise HTTPException(404)
    return FileResponse(p)


# ------------------------------------------------------------------ frontend (production build)
if FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        f = FRONTEND_DIST / path
        return FileResponse(f if f.is_file() else FRONTEND_DIST / "index.html")
