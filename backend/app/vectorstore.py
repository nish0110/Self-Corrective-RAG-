"""ChromaDB wrapper (persistent, cosine distance, embeddings supplied by us)."""
from __future__ import annotations

import threading
import time
from collections import defaultdict
from typing import Optional

import chromadb
from chromadb.config import Settings as ChromaSettings

from .config import settings
from .embeddings import get_embedder
from .models import Document


class VectorStore:
    def __init__(self, path: Optional[str] = None, collection: Optional[str] = None) -> None:
        self.embedder = get_embedder()
        self.client = chromadb.PersistentClient(
            path=path or settings.chroma_dir,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        # One collection per embedding model: vectors from different models are not comparable.
        safe = "".join(c if c.isalnum() else "_" for c in self.embedder.name)
        self.collection_name = collection or f"crag_{safe}"[:60]
        self.col = self.client.get_or_create_collection(
            self.collection_name, metadata={"hnsw:space": "cosine"}
        )

    # ---------------- write ----------------
    def add(self, chunks: list[dict]) -> int:
        """chunks: [{"id", "text", "metadata"}]"""
        if not chunks:
            return 0
        ids = [c["id"] for c in chunks]
        texts = [c["text"] for c in chunks]
        metas = [{**c["metadata"], "ingested_at": int(time.time())} for c in chunks]
        embs = self.embedder.embed_documents(texts)
        for i in range(0, len(ids), 256):
            self.col.upsert(ids=ids[i:i + 256], documents=texts[i:i + 256],
                            metadatas=metas[i:i + 256], embeddings=embs[i:i + 256])
        return len(ids)

    def delete_source(self, source: str) -> int:
        got = self.col.get(where={"source": source})
        if got["ids"]:
            self.col.delete(ids=got["ids"])
        return len(got["ids"])

    def reset(self) -> None:
        self.client.delete_collection(self.collection_name)
        self.col = self.client.get_or_create_collection(
            self.collection_name, metadata={"hnsw:space": "cosine"}
        )

    # ---------------- read ----------------
    def count(self) -> int:
        return self.col.count()

    def search(self, query: str, k: int) -> list[Document]:
        n = self.count()
        if n == 0:
            return []
        res = self.col.query(
            query_embeddings=[self.embedder.embed_query(query)],
            n_results=min(k, n),
            include=["documents", "metadatas", "distances"],
        )
        out = []
        for id_, text, meta, dist in zip(res["ids"][0], res["documents"][0],
                                         res["metadatas"][0], res["distances"][0]):
            out.append(Document(
                id=id_, text=text, source=meta.get("source", "?"), origin="local",
                title=meta.get("title", meta.get("source", "")),
                similarity=round(1 - dist, 4), metadata=meta,
            ))
        return out

    def list_sources(self) -> list[dict]:
        got = self.col.get(include=["metadatas"])
        agg: dict[str, dict] = defaultdict(lambda: {"chunks": 0})
        for m in got["metadatas"]:
            s = agg[m.get("source", "?")]
            s["chunks"] += 1
            s["source"] = m.get("source", "?")
            s["title"] = m.get("title", s["source"])
            s["ingested_at"] = m.get("ingested_at")
            s["pages"] = max(s.get("pages", 0), int(m.get("page", 0) or 0))
        return sorted(agg.values(), key=lambda x: x["source"])


_store: Optional[VectorStore] = None
_lock = threading.Lock()


def get_store() -> VectorStore:
    """Thread-safe singleton (ChromaDB crashes if two clients are created concurrently)."""
    global _store
    if _store is None:
        with _lock:
            if _store is None:
                _store = VectorStore()
    return _store


def set_store(store: Optional[VectorStore]) -> None:
    global _store
    _store = store
