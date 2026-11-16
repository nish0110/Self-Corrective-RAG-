from app.config import settings
from app.evaluator import AMBIGUOUS, CORRECT, INCORRECT, decide_action
from app.ingest import chunk_text
from app.llm import parse_json
from app.models import Document
from app.pipeline import run_baseline, run_crag
from app.textutils import is_time_sensitive, split_sentences


# ---------------------------------------------------------------- units
def test_chunker_respects_size_and_overlap():
    text = "\n\n".join(f"Paragraph {i}. " + "word " * 60 for i in range(10))
    chunks = chunk_text(text, size=400, overlap=50)
    assert len(chunks) > 3
    assert all(len(c) <= 460 for c in chunks)


def test_parse_json_tolerates_fences_and_prose():
    assert parse_json('```json\n{"score": 0.8}\n```') == {"score": 0.8}
    assert parse_json('Sure! {"query": "x"} hope that helps') == {"query": "x"}
    assert parse_json("nonsense") == {}


def test_sentence_splitter_handles_markdown_lists():
    s = split_sentences("## Title\n- First rule.\n- Second rule. Another sentence.")
    assert s == ["Title", "First rule.", "Second rule.", "Another sentence."]


def test_time_sensitivity_detection():
    assert is_time_sensitive("What is the latest version of PyTorch?")
    assert not is_time_sensitive("How does attention work?")


def _docs(*scores):
    return [Document(id=str(i), text="", source="s", relevance=s) for i, s in enumerate(scores)]


def test_action_thresholds():
    settings.update({"upper_threshold": 0.7, "lower_threshold": 0.3})
    assert decide_action(_docs(0.9, 0.1)) == CORRECT
    assert decide_action(_docs(0.5, 0.2)) == AMBIGUOUS
    assert decide_action(_docs(0.2, 0.1)) == INCORRECT
    assert decide_action([]) == INCORRECT


# ---------------------------------------------------------------- routes
def test_correct_route_uses_local_only():
    r = run_crag("What are the GPU booking limits for the Tensor-1 server?")
    assert r["action"] == CORRECT
    assert r["route"] == "local"
    assert r["metrics"]["web_searches"] == 0
    assert all(s["source"] == "aiml_lab_handbook.md" for s in r["sources"])
    assert "[1]" in r["answer"]


def test_incorrect_route_rewrites_then_searches_web():
    r = run_crag("Who won the 2022 FIFA World Cup?")
    assert r["action"] == INCORRECT
    assert r["metrics"]["retrieval_attempts"] == 1 + settings.max_rewrites
    assert any(rw["purpose"] == "retrieval" for rw in r["rewrites"])
    assert any(rw["purpose"] == "web" for rw in r["rewrites"])
    assert r["route"] == "web"
    assert "Argentina" in r["answer"]


def test_time_sensitive_question_distrusts_outdated_local_docs():
    r = run_crag("What are the latest features in the newest Python release?")
    assert r["time_sensitive"]
    assert r["action"] in (AMBIGUOUS, INCORRECT)
    assert r["metrics"]["web_searches"] >= 1
    assert any(s["origin"] == "web" for s in r["sources"])


def test_baseline_never_searches_web():
    r = run_baseline("Who won the 2022 FIFA World Cup?")
    assert r["metrics"]["web_searches"] == 0
    assert all(s["origin"] == "local" for s in r["sources"])


def test_web_disabled_gives_honest_answer():
    from app import websearch
    websearch.set_search_override(None)
    settings.update({"web_search_provider": "none"})
    r = run_crag("Who won the 2022 FIFA World Cup?")
    assert "insufficient" in r["answer"].lower()


def test_stream_emits_steps_in_order():
    from app.pipeline import crag_stream
    nodes = [e["node"] for e in crag_stream("How was CLIP trained?") if e["type"] == "step"]
    assert nodes[:4] == ["query", "retrieve", "evaluate", "route"]
    assert "generate" in nodes
