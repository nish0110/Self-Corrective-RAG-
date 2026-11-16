import json

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    r = client.get("/api/health").json()
    assert r["status"] == "ok" and r["chunks"] > 0 and r["llm"]["mock"]


def test_config_update_roundtrip():
    r = client.put("/api/config", json={"top_k": 6, "upper_threshold": 0.8}).json()
    assert r["top_k"] == 6 and r["upper_threshold"] == 0.8
    assert "llm_api_key" not in r


def test_upload_and_delete_document():
    files = {"files": ("notes.txt", b"The secret project codename is BLUE HERON. It started in 2021.", "text/plain")}
    r = client.post("/api/documents/upload", files=files).json()
    assert r["results"][0]["chunks"] == 1
    ans = client.post("/api/query", json={"query": "What is the secret project codename?"}).json()
    assert "BLUE HERON" in ans["answer"]
    assert client.delete("/api/documents/notes.txt").json()["deleted_chunks"] == 1


def test_stream_endpoint():
    with client.stream("POST", "/api/query/stream", json={"query": "What is HNSW?"}) as r:
        events = [json.loads(line[6:]) for line in r.iter_lines() if line.startswith("data: ")]
    assert events[-1]["type"] == "result"
    assert any(e["type"] == "step" and e["node"] == "evaluate" for e in events)


def test_compare_endpoint():
    r = client.post("/api/compare", json={"query": "Who won the 2022 FIFA World Cup?"}).json()
    assert r["baseline"]["mode"] == "baseline" and r["crag"]["mode"] == "crag"


def test_evaluation_harness_small():
    from app import evaluation
    items = [i for i in evaluation.load_testset() if i["id"] in ("L1", "M1")]
    rep = evaluation.run_evaluation(items, save=False)
    o = rep["summary"]["overall"]
    assert o["crag"]["routing_correct"] == 1.0
    assert o["crag"]["correctness"] >= o["baseline"]["correctness"]
