import { Fragment, useEffect, useRef, useState } from "react";
import { api } from "../api";
import { Spinner } from "../components/ui";

const ROWS = [
  ["context_relevance", "Context relevance", true],
  ["faithful", "Faithfulness", true],
  ["hallucination_rate", "Hallucination rate", false],
  ["answer_relevance", "Answer relevance", true],
  ["correctness", "Key-fact correctness", true],
  ["precision", "Context precision", true],
  ["recall", "Context recall", true],
  ["mrr", "MRR", true],
  ["topk_hit", "Top-k accuracy", true],
  ["routing_correct", "Routing accuracy", true],
  ["web_search", "Web-search usage", null],
  ["retrieval_attempts", "Retrieval attempts", null],
  ["llm_calls", "LLM calls", null],
  ["tokens", "Tokens / query", null],
  ["latency_ms", "Latency (ms)", false],
];
const CATS = ["local", "missing", "ambiguous", "time_sensitive", "distractor"];

const fmt = (v) => v == null ? "—" : Math.abs(v) >= 100 ? Math.round(v).toLocaleString() : v.toFixed(2);

function Bars({ b, c }) {
  return (
    <div className="bars">
      <div className="bar b" style={{ width: `${(b || 0) * 100}%` }} />
      <div className="bar c" style={{ width: `${(c || 0) * 100}%` }} />
    </div>
  );
}

export default function EvalPage() {
  const [data, setData] = useState(null);
  const [status, setStatus] = useState(null);
  const [limit, setLimit] = useState("");
  const [cat, setCat] = useState("");
  const [err, setErr] = useState("");
  const [open, setOpen] = useState(null);
  const timer = useRef(null);

  const load = () => api.evalResults().then(setData).catch((e) => setErr(e.message));
  useEffect(() => {
    load();
    api.evalStatus().then((s) => { setStatus(s); if (s.running) poll(); });
    return () => clearInterval(timer.current);
  }, []);

  function poll() {
    clearInterval(timer.current);
    timer.current = setInterval(async () => {
      const s = await api.evalStatus();
      setStatus(s);
      if (!s.running) { clearInterval(timer.current); load(); if (s.error) setErr(s.error); }
    }, 1200);
  }

  async function start() {
    setErr("");
    try { setStatus(await api.runEval(limit || null, cat || null)); poll(); }
    catch (e) { setErr(e.message); }
  }

  const o = data?.summary?.overall;
  const running = status?.running;

  return (
    <div className="page">
      <div className="page-head"><div><h2>Evaluation</h2>
      <p className="lead">Benchmarks <b>traditional RAG vs CRAG</b> on the test set in
        <code> backend/evaluation/testset.json</code>, covering five query categories: local, missing, ambiguous,
        time-sensitive and distractor. Scores come from LLM judges (faithfulness, relevance, key-fact correctness),
        gold source labels (precision / recall / MRR) and pipeline counters.</p></div></div>

      <div className="row gap">
        <select value={cat} onChange={(e) => setCat(e.target.value)} disabled={running}>
          <option value="">All categories</option>
          {CATS.map((c) => <option key={c} value={c}>{c}</option>)}
        </select>
        <input className="small" type="number" min="1" placeholder="limit" value={limit}
          onChange={(e) => setLimit(e.target.value)} disabled={running} />
        <button className="btn primary" onClick={start} disabled={running}>Run evaluation</button>
        {running && (
          <span className="progress">
            <Spinner /> {status.done}/{status.total} — {status.current}
            <span className="pbar"><span style={{ width: `${(100 * status.done) / (status.total || 1)}%` }} /></span>
          </span>
        )}
      </div>
      {err && <div className="error">{err}</div>}

      {!data?.available && !running && <div className="muted pad">No results yet. Load the sample knowledge base, then run the evaluation (with a real LLM it makes roughly 15 LLM calls per question).</div>}

      {o && (
        <>
          <div className="muted small-print">Last run {data.created_at} · {data.n_questions} questions · LLM <code>{data.llm}</code></div>
          <div className="eval-grid">
            <div className="panel">
              <h3>Overall</h3>
              <table className="table">
                <thead><tr><th>Metric</th><th className="num">Traditional RAG</th><th className="num">CRAG</th><th className="w40" /></tr></thead>
                <tbody>
                  {ROWS.map(([k, label, higher]) => {
                    const b = o.baseline?.[k], c = o.crag?.[k];
                    const better = higher == null || b == null || c == null ? null : higher ? c > b : c < b;
                    return (
                      <tr key={k}>
                        <td>{label}{higher === false && <small className="muted"> ↓ lower is better</small>}</td>
                        <td className="num">{fmt(b)}</td>
                        <td className={`num ${better === true ? "ok" : better === false && c !== b ? "bad" : ""}`}>{fmt(c)}</td>
                        <td>{higher !== null && (b ?? 0) <= 1 && (c ?? 0) <= 1 && <Bars b={b} c={c} />}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
              <div className="legend"><span><i className="sw base" /> Traditional RAG</span><span><i className="sw crag" /> CRAG</span></div>
            </div>
            <div className="panel">
              <h3>Correctness by category</h3>
              {Object.entries(data.summary.by_category).map(([c, v]) => (
                <div key={c} className="catrow">
                  <div className="catname">{c.replace("_", "-")}</div>
                  <Bars b={v.baseline?.correctness} c={v.crag?.correctness} />
                  <div className="catnums mono">{fmt(v.baseline?.correctness)} → {fmt(v.crag?.correctness)}</div>
                  <div className="muted tiny">CRAG web use {fmt(v.crag?.web_search)} · routing {fmt(v.crag?.routing_correct)}</div>
                </div>
              ))}
            </div>
          </div>

          <div className="panel">
            <h3>Per-question results</h3>
            <table className="table compact">
              <thead><tr><th>ID</th><th>Category</th><th>Question</th><th>System</th><th>Route</th>
                <th className="num">Correct</th><th className="num">Faithful</th><th className="num">ms</th></tr></thead>
              <tbody>
                {data.rows.map((r, i) => (
                  <Fragment key={i}>
                    <tr className="clickable" onClick={() => setOpen(open === i ? null : i)}>
                      <td className="mono">{r.id}</td><td>{r.category}</td>
                      <td className="q">{r.system === "baseline" ? r.question : ""}</td>
                      <td>{r.system === "crag" ? <b>CRAG</b> : "RAG"}</td>
                      <td>{r.route && <span className={`badge route-${r.route}`}>{r.route}</span>}</td>
                      <td className="num">{fmt(r.correctness)}</td>
                      <td className="num">{fmt(r.faithful)}</td>
                      <td className="num">{fmt(r.latency_ms)}</td>
                    </tr>
                    {open === i && <tr className="detail"><td colSpan={8}>{r.answer}</td></tr>}
                  </Fragment>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
