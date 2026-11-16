"""Test setup: offline mock LLM, hash embeddings, temporary ChromaDB, fake web search."""
import os
import tempfile

os.environ["LLM_PROVIDER"] = "mock"
os.environ["EMBEDDING_BACKEND"] = "hash"
os.environ["EVALUATOR_BACKEND"] = "llm"
os.environ["CHROMA_DIR"] = tempfile.mkdtemp(prefix="crag-test-")

import pytest  # noqa: E402

from app.config import BACKEND_DIR, settings  # noqa: E402
from app.ingest import ingest_directory  # noqa: E402
from app.models import Document  # noqa: E402
from app.vectorstore import get_store  # noqa: E402
from app import websearch  # noqa: E402

FAKE_WEB = {
    "fifa": ("https://example.org/fifa-2022", "2022 FIFA World Cup final",
             "Argentina won the 2022 FIFA World Cup, beating France on penalties in the final in Qatar."),
    "python": ("https://example.org/python-3-14", "What's new in Python",
               "The newest Python release adds template strings, deferred evaluation of annotations "
               "and an officially supported free-threaded build."),
}


def fake_search(query: str, n: int):
    ql = query.lower()
    out = []
    for key, (url, title, text) in FAKE_WEB.items():
        if key in ql:
            out.append(Document(id="web-" + key, text=text, source=url, origin="web", title=title, similarity=0.9))
    return out


@pytest.fixture(scope="session", autouse=True)
def knowledge_base():
    store = get_store()
    store.reset()
    ingest_directory(store, BACKEND_DIR / "data" / "sample_docs")
    return store


@pytest.fixture(autouse=True)
def web(monkeypatch):
    websearch.set_search_override(fake_search)
    snapshot = {k: getattr(settings, k) for k in settings.RUNTIME_FIELDS}
    yield
    websearch.set_search_override(None)
    settings.update(snapshot)
