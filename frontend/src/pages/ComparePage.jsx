import { useState } from "react";
import { api } from "../api";
import { ActionBadge, AnswerText, DocCard, Metrics, RouteBadge, Spinner } from "../components/ui";

const EXAMPLES = [
  "Who won the 2022 FIFA World Cup?",
  "What are the latest features in the newest Python release?",
  "What new features were introduced in Python 3.13?",
  "lab gpu rules?",
];

function Column({ title, sub, r }) {
  return (
    <div className="cmp-col">
      <div className="cmp-head">
        <h3>{title}</h3>
        <span className="muted">{sub}</span>
      </div>
      {!r ? <div className="muted pad"><Spinner /> waiting…</div> : (
        <>
          <div className="answer-top">
            <RouteBadge route={r.route} /><ActionBadge action={r.action} />
            {r.confidence != null && <span className="conf">confidence <b>{Math.round(r.confidence * 100)}%</b></span>}
          </div>
          <AnswerText text={r.answer} />
          <Metrics m={r.metrics} />
          <h4>Context given to the LLM ({r.sources.length})</h4>
          {r.sources.map((s) => <DocCard key={s.n + s.id} doc={s} n={s.n} showScore={r.mode === "crag"} compact />)}
        </>
      )}
    </div>
  );
}

export default function ComparePage() {
  const [q, setQ] = useState("");
  const [res, setRes] = useState(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  async function run(text) {
    const question = (text ?? q).trim();
    if (!question) return;
    setQ(question); setBusy(true); setErr(""); setRes({});
    try {
      const [b, c] = await Promise.all([api.query(question, "baseline"), api.query(question, "crag")]);
      setRes({ baseline: b, crag: c });
    } catch (e) { setErr(e.message); setRes(null); }
    finally { setBusy(false); }
  }

  return (
    <div className="page">
      <div className="page-head"><div>
        <h2>CRAG vs traditional RAG</h2>
        <p className="lead">The same question through both pipelines. Traditional RAG trusts whatever it retrieves; CRAG grades it, routes and corrects.</p>
      </div></div>
      <form className="askbox inline" onSubmit={(e) => { e.preventDefault(); run(); }}>
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Question to compare…" />
        <button className="btn primary" disabled={busy || !q.trim()}>{busy ? "Running…" : "Compare"}</button>
      </form>
      <div className="examples">
        {EXAMPLES.map((ex) => <button key={ex} className="example" onClick={() => run(ex)} disabled={busy}>{ex}</button>)}
      </div>
      {err && <div className="error">{err}</div>}
      {res && (
        <div className="cmp">
          <Column title="Traditional RAG" sub="trusts whatever the retriever returns" r={res.baseline} />
          <Column title="CRAG" sub="evaluates, routes and self-corrects" r={res.crag} />
        </div>
      )}
    </div>
  );
}
