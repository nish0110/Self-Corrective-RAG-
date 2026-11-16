"""Small dependency-free text helpers (tokenising, sentence splitting, overlap)."""
from __future__ import annotations

import re

STOPWORDS = set("""
a an the and or but if then else of to in on at by for with from into onto about as is are was were be been
being do does did doing have has had having i me my we our you your he she it its they them their this that
these those what which who whom whose when where why how there here can could should would will shall may
might must not no nor so than too very just also only own same such both each few more most other some any
all again further once up down out over under between through during before after above below off s t don
now tell explain describe give list please show find get thing things kind use used using one two vs
""".split())

TIME_SENSITIVE = re.compile(
    r"\b(latest|current(ly)?|recent(ly)?|newest|today|this (year|month|week)|right now|"
    r"as of|upcoming|new features|202[4-9]|203\d)\b",
    re.I,
)

_WORD = re.compile(r"[a-z0-9][a-z0-9\.\-\+#]*", re.I)


def stem(w: str) -> str:
    w = w.lower().strip(".-")
    for suf in ("ings", "ing", "ies", "ied", "ers", "ed", "es", "s", "ly"):
        if len(w) > len(suf) + 3 and w.endswith(suf):
            return w[: -len(suf)]
    return w


def tokens(text: str) -> list[str]:
    return [stem(t) for t in _WORD.findall(text) if t.lower() not in STOPWORDS and len(t) > 1]


def keyword_set(text: str) -> set[str]:
    return set(tokens(text))


def coverage(query: str, text: str) -> float:
    """Fraction of the query's keywords that appear in text (0..1)."""
    q = keyword_set(query)
    if not q:
        return 0.0
    t = keyword_set(text)
    return len(q & t) / len(q)


def split_sentences(text: str) -> list[str]:
    """Split on sentence ends, and treat markdown lines / bullets as separate sentences."""
    out: list[str] = []
    for line in re.split(r"\n+|\s+…\s+", text):
        line = re.sub(r"^\s*(#+|[-*•]|\d+[\.\)])\s+", "", line)
        line = re.sub(r"\s+", " ", line).strip()
        if not line:
            continue
        parts = re.split(r"(?<=[\.\!\?])\s+(?=[A-Z0-9\"'(\[])", line)
        out.extend(p.strip() for p in parts if p.strip())
    return out


def is_time_sensitive(query: str) -> bool:
    return bool(TIME_SENSITIVE.search(query))
