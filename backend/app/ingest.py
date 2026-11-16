"""Document loading + chunking (PDF, TXT, MD, DOCX, CSV, HTML)."""
from __future__ import annotations

import hashlib
import io
import re
from pathlib import Path

from .config import settings

SUPPORTED = {".pdf", ".txt", ".md", ".markdown", ".docx", ".csv", ".html", ".htm"}


# ---------------------------------------------------------------- loaders
def load_bytes(filename: str, data: bytes) -> list[tuple[str, dict]]:
    """Return a list of (text, metadata) "pages" for a file."""
    ext = Path(filename).suffix.lower()
    if ext not in SUPPORTED:
        raise ValueError(f"Unsupported file type {ext}. Supported: {', '.join(sorted(SUPPORTED))}")
    if ext == ".pdf":
        from pypdf import PdfReader

        try:
            reader = PdfReader(io.BytesIO(data))
            if reader.is_encrypted:
                reader.decrypt("")
            return [((p.extract_text() or ""), {"page": i + 1}) for i, p in enumerate(reader.pages)]
        except Exception as e:
            raise ValueError(f"Could not read this PDF ({e}). Is it password-protected or damaged?") from e
    if ext == ".docx":
        try:
            import docx  # python-docx
        except ImportError as e:
            raise ValueError("Install python-docx to ingest .docx files") from e
        d = docx.Document(io.BytesIO(data))
        return [("\n".join(p.text for p in d.paragraphs), {"page": 1})]
    encs = ("utf-16",) if data[:2] in (b"\xff\xfe", b"\xfe\xff") else ("utf-8-sig", "cp1252", "latin-1")
    for enc in encs:
        try:
            text = data.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    if ext in (".html", ".htm"):
        text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", text, flags=re.S | re.I)
        text = re.sub(r"<[^>]+>", " ", text)
    return [(text, {"page": 1})]


def guess_title(filename: str, first_text: str) -> str:
    m = re.search(r"^\s*#\s+(.+)$", first_text, flags=re.M)
    if m:
        return m.group(1).strip()
    return Path(filename).stem.replace("_", " ").replace("-", " ").title()


# ---------------------------------------------------------------- chunking
_SEPARATORS = ["\n## ", "\n### ", "\n\n", "\n", ". ", " "]


def _split(text: str, size: int, seps: list[str]) -> list[str]:
    if len(text) <= size:
        return [text]
    if not seps:
        return [text[i:i + size] for i in range(0, len(text), size)]
    sep, rest = seps[0], seps[1:]
    parts = text.split(sep)
    if len(parts) == 1:
        return _split(text, size, rest)
    # Re-attach the separator so that joining pieces reproduces the original text:
    # headings stay at the start of their section, other separators stay at the end.
    if sep.startswith("\n#"):
        parts = [parts[0]] + [sep + p for p in parts[1:]]
    else:
        parts = [p + sep for p in parts[:-1]] + [parts[-1]]
    pieces, buf = [], ""
    for part in parts:
        candidate = buf + part
        if len(candidate) <= size:
            buf = candidate
        else:
            if buf:
                pieces.append(buf)
            if len(part) > size:
                pieces.extend(_split(part, size, rest))
                buf = ""
            else:
                buf = part
    if buf:
        pieces.append(buf)
    return pieces


def chunk_text(text: str, size: int | None = None, overlap: int | None = None) -> list[str]:
    """Recursive character splitter (same idea as LangChain's RecursiveCharacterTextSplitter)."""
    size = size or settings.chunk_size
    overlap = settings.chunk_overlap if overlap is None else overlap
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if not text:
        return []
    raw = [p.strip() for p in _split(text, size, _SEPARATORS) if p.strip()]
    if overlap <= 0 or len(raw) < 2:
        return raw
    out = [raw[0]]
    for prev, cur in zip(raw, raw[1:]):
        tail = prev[-overlap:]
        cut = tail.find(" ")
        tail = tail[cut + 1:] if 0 <= cut < len(tail) - 1 else tail
        out.append(f"{tail}\n{cur}".strip())
    return out


def build_chunks(filename: str, data: bytes) -> list[dict]:
    pages = load_bytes(filename, data)
    title = guess_title(filename, pages[0][0] if pages else "")
    digest = hashlib.sha1(data).hexdigest()[:10]
    chunks = []
    for text, meta in pages:
        for j, ch in enumerate(chunk_text(text)):
            cid = f"{digest}-p{meta.get('page', 1)}-c{j}"
            chunks.append({
                "id": cid,
                "text": ch,
                "metadata": {"source": filename, "title": title, "page": meta.get("page", 1), "chunk": j},
            })
    return chunks


def ingest_file(store, filename: str, data: bytes) -> dict:
    if not data:
        raise ValueError("The file is empty.")
    chunks = build_chunks(filename, data)
    if not chunks:
        raise ValueError("No text could be extracted. If this is a scanned PDF (images of pages), "
                         "run OCR on it first or upload a text-based version.")
    store.delete_source(filename)  # re-uploading a file replaces it
    n = store.add(chunks)
    return {"source": filename, "chunks": n}


def ingest_directory(store, folder: Path) -> list[dict]:
    results = []
    for p in sorted(folder.iterdir()):
        if p.suffix.lower() in SUPPORTED:
            results.append(ingest_file(store, p.name, p.read_bytes()))
    return results
