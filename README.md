# Self-Corrective RAG (CRAG) with Fallback Web Search and Routing

A question-answering system that **checks whether its retrieved documents are actually relevant before answering**. If they aren't, it **corrects itself**: it rewrites the query, retries retrieval, falls back to web search (Tavily), and finally validates the answer for groundedness.

Based on *Corrective Retrieval Augmented Generation*, Yan et al., 2024.

```
question ─► Vector search (ChromaDB) ─► Retrieval evaluator (scores 0–1 per doc) ─► Router
   CORRECT   (any doc ≥ upper)  → refine local docs ───────────────────────────► Generate ─► Validate ─► Answer
   AMBIGUOUS (in between)       → keep partly-relevant docs + rewrite → Web ───► Generate ─► Validate
   INCORRECT (all < lower)      → rewrite → re-retrieve (loop) → still bad? discard local → Web → Generate
   Validation FAIL              → self-correct: escalate to web search, or regenerate strictly
```

## Features (mapped to the project spec)

| Requirement | Where |
|---|---|
| Retrieval evaluator that scores retrieved docs | `backend/app/evaluator.py`: LLM-as-judge (default), cross-encoder, or embedding backends |
| Dynamic routing: high → generate, low/ambiguous → web, incorrect → rewrite | `backend/app/pipeline.py` (`crag_stream`) |
| Query rewriting (for re-retrieval and for web search) | `backend/app/rewriter.py` |
| Web search fallback (Tavily, with DuckDuckGo as a no-key backup) | `backend/app/websearch.py` |
| Knowledge refinement (decompose → filter → recompose strips) | `backend/app/refiner.py` |
| Answer validation + self-correction loop | `backend/app/generator.py`, `pipeline.py` |
| Out-of-date knowledge detection | Time-sensitive questions make the grader distrust old local docs |
| Baseline (traditional RAG) for comparison | `run_baseline` in `pipeline.py` |
| Evaluation: precision, recall, MRR, top-k, faithfulness, answer/context relevance, hallucination rate, latency, web usage, tokens, routing accuracy | `backend/app/evaluation.py`, `backend/evaluation/testset.json` (25 questions in 5 categories) |
| React UI: chat with live step pills, relevance scores, step log and flow diagram per answer; citations; CRAG-vs-RAG comparison; document upload; evaluation dashboard; settings; system check | `frontend/` |

**Tech stack:** React + Vite · FastAPI · ChromaDB · sentence-transformers (all-MiniLM-L6-v2) · any OpenAI-compatible LLM (Groq / Gemini / OpenAI / Ollama) · Tavily · PyPDF.

The pipeline is written as plain Python functions instead of LangChain/LangGraph. Each step is about 30 readable lines, and you can explain every line in the viva. The chunker follows the same design as LangChain's `RecursiveCharacterTextSplitter`.

---

## Setup

Requirements: Python 3.10+, Node 18+.

### 1. Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt    # first run downloads PyTorch + the embedding model (~1 GB total)
cp .env.example .env               # then edit .env
```

Free API keys:
- **LLM**: Groq, https://console.groq.com → put `LLM_PROVIDER=groq` and `LLM_API_KEY=gsk_...` (default model `openai/gpt-oss-120b`)
  (or Gemini via https://aistudio.google.com with `LLM_PROVIDER=gemini`, or run Ollama locally with `LLM_PROVIDER=ollama`, which needs no key)
- **Web search**: Tavily, https://tavily.com → `TAVILY_API_KEY=tvly-...` (without it, DuckDuckGo is used)

```bash
python -m app.cli ingest                                   # load the sample knowledge base
python -m app.cli ask "Who won the 2022 FIFA World Cup?"   # see every CRAG step in the terminal

```

### 2. Run it (easiest: one command, one URL)

```bash
./start.sh        # macOS / Linux
start.bat         # Windows
```

This builds the UI once and serves everything at **http://127.0.0.1:8000**. If your frontend changes don't show up, delete `frontend/dist` and run the script again.

**For UI development** (hot reload) use two terminals instead:

```bash
# terminal 1
cd backend && uvicorn app.main:app --host 127.0.0.1 --port 8000
# terminal 2
cd frontend && npm install && npm run dev      # http://127.0.0.1:5173
```

Then open **System check** in the sidebar. Every component should be green (web search can be yellow).

## Troubleshooting

| Symptom | Fix |
|---|---|
| Everything fails, or the sidebar says "Backend offline" | The backend isn't running. Start it and keep that terminal open. |
| "Model ... is not available" | Providers retire models. The app now switches to an available model automatically; to pick one yourself, set `LLM_MODEL` (Groq list: console.groq.com/docs/models). |
| "API key was rejected" | Check `LLM_API_KEY` in `backend/.env`, and that `LLM_PROVIDER` matches the key. |
| "Rate limit reached" | Free tiers allow only a few requests per minute. Wait, or set `EVALUATOR_BACKEND=embedding` to make fewer LLM calls. |
| An upload shows "No text could be extracted" | The PDF is scanned images. Run OCR on it first, or upload a text-based PDF. |
| Embeddings show `hash-768` | sentence-transformers didn't install or couldn't download its model. Run `pip install sentence-transformers` with internet on, then restart. |
| Retrieval looks wrong after switching embedding models | Delete `backend/storage/`, restart, and re-upload. |

### Demo mode (no keys, no internet)

Set `LLM_PROVIDER=mock` and `EMBEDDING_BACKEND=hash` (and optionally `WEB_SEARCH_PROVIDER=none`). The whole app then runs offline with a transparent heuristic "LLM". This mode is useful as a backup if the Wi-Fi fails during your review. The answers are extractive and crude, so **use a real LLM for evaluation numbers**.

### Tests

```bash
cd backend && python -m pytest -q     # 17 tests, run fully offline
```

---

## Demo script (for the review)

The sample docs in `backend/data/sample_docs/` are designed so that each route can be shown on purpose. The example buttons on the Ask page cover all five categories.

| Category | Question | Expected behaviour |
|---|---|---|
| Local | "What are the GPU booking limits for the Tensor-1 server?" | **CORRECT**: answered only from the internal lab handbook, no web search |
| Missing | "Who won the 2022 FIFA World Cup?" | **INCORRECT**: rewrite, retry, then web search |
| Ambiguous | "how do picture generators get rid of the noise?" | Vague wording; evaluator and rewriting recover the diffusion doc |
| Time-sensitive | "What are the latest features in the newest Python release?" | The KB has 2023 notes calling 3.12 "latest"; the evaluator caps them, so CRAG goes to the web, while traditional RAG gives the outdated answer |
| Distractor | "What new features were introduced in Python 3.13?" | Similar-looking but wrong doc gets rejected, then web |

Use the **CRAG vs RAG** tab on the time-sensitive and missing questions to show the difference side by side.

## Evaluation

```bash
python -m app.cli eval                    # all 25 questions, both systems
python -m app.cli eval --category local --limit 3
python -m app.cli eval --delay 2          # slow down for free-tier rate limits
```

Results are saved to `backend/evaluation/results/` (`latest.md`, `latest.csv`, `latest.json`, `quality.png`, `by_category.png`) and shown on the Evaluation page. Expect about 15 LLM calls per question with an LLM evaluator. To cut calls, set `EVALUATOR_BACKEND=cross_encoder`.

## Configuration knobs

All knobs are in `.env`, and most can also be changed live on the Settings page: `UPPER_THRESHOLD` (0.7), `LOWER_THRESHOLD` (0.3), `TOP_K` (4), `MAX_REWRITES` (1), `EVALUATOR_BACKEND`, `ENABLE_REFINEMENT`, `ENABLE_VALIDATION`, `MAX_VALIDATION_RETRIES`, `WEB_SEARCH_PROVIDER`.

### Member 1 handoff

- Copy `backend/.env.example` to `backend/.env`.
- Set `LLM_PROVIDER=groq` and a newly issued `LLM_API_KEY`; the default model is `openai/gpt-oss-120b`.
- Set `TAVILY_API_KEY` and `WEB_SEARCH_PROVIDER=tavily`, or use `WEB_SEARCH_PROVIDER=duckduckgo` without a Tavily key.
- Keep `EMBEDDING_BACKEND=sentence-transformers` and `EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2` for 384-dimensional MiniLM embeddings.
- `sentence-transformers`, `sentence_transformers`, and `auto` are accepted embedding backend values.
- Rotate any previously shared Groq or Tavily key in the provider console; do not commit `.env` or paste credentials into source files.
- Restart the backend after changing provider keys or embedding settings.

## API

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/query` | `{query, mode: "crag"|"baseline"}` → full result |
| POST | `/api/query/stream` | Same, as server-sent events (one per step) |
| POST | `/api/compare` | Runs both systems |
| GET | `/api/diagnostics` | Tests LLM, embeddings, vector DB, web search |
| GET/POST/DELETE | `/api/documents…` | List, upload, load samples, delete, reset |
| GET/PUT | `/api/config` | Runtime settings |
| POST/GET | `/api/eval/run`, `/api/eval/status`, `/api/eval/results` | Evaluation |

## Project structure

```
backend/
  app/
    config.py       settings (.env)            pipeline.py    CRAG graph + baseline
    llm.py          OpenAI-compatible + mock   evaluator.py   retrieval evaluator + action
    embeddings.py   MiniLM / hash              refiner.py     decompose-recompose
    vectorstore.py  ChromaDB                   rewriter.py    query rewriting
    ingest.py       loaders + chunker          websearch.py   Tavily / DuckDuckGo
    prompts.py      all prompts                generator.py   generation + validation
    evaluation.py   metrics + report           main.py        FastAPI   cli.py  CLI
  data/sample_docs/  evaluation/testset.json  tests/
frontend/src/  App.jsx  pages/{Ask,Compare,Knowledge,Eval,Settings}Page.jsx  components/{Pipeline,ui}.jsx
```

## Possible extensions (future scope)

Multimodal RAG (embed images with CLIP, which fits Unit 4) · multiple search providers · RL or adaptive thresholds · knowledge-graph retrieval · conversation memory.
