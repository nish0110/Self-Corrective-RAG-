import { useEffect, useRef, useState } from "react";
import { streamQuery } from "../api";
import Icon from "../components/icons";
import Pipeline from "../components/Pipeline";
import { ActionBadge, AnswerText, DocCard, Metrics, NODE_LABEL, RouteBadge, Spinner } from "../components/ui";

const EXAMPLES = [
  ["Local knowledge", "What are the GPU booking limits for the Tensor-1 server in the AI lab?", "Answered from your documents"],
  ["Missing knowledge", "Who won the 2022 FIFA World Cup?", "Not in documents → web"],
  ["Ambiguous", "how do picture generators get rid of the noise?", "Vague wording → rewrite"],
  ["Time-sensitive", "What are the latest features in the newest Python release?", "Outdated docs → web"],
  ["Distractor", "What new features were introduced in Python 3.13?", "Similar but wrong doc → web"],
];

/* ---------- live step pills ---------- */
function Stepper({ steps, active, running }) {
  return (
    <div className="stepper">
      {steps.map((s, i) => (
        <span key={i} className={`pill-step n-${s.node} ${s.node === "route" ? "act-" + (s.data?.action || "").toLowerCase() : ""} ${s.node === "validate" ? (s.data?.passed ? "pass" : "fail") : ""}`}
          title={s.summary}>
          {s.node === "route" ? s.data?.action?.toLowerCase() : NODE_LABEL[s.node] || s.node}
        </span>
      ))}
      {running && active && active !== "final" && (
        <span className={`pill-step n-${active} live`}><Spinner />{NODE_LABEL[active] || active}</span>
      )}
    </div>
  );
}

/* ---------- "How CRAG answered" ---------- */
function Details({ turn }) {
  const [tab, setTab] = useState("scores");
  const r = turn.result;
  const evals = turn.steps.filter((s) => s.node === "evaluate");
  return (
    <div className="details">
      <div className="tabs">
        {turn.mode === "crag" && <button className={tab === "scores" ? "on" : ""} onClick={() => setTab("scores")}>Relevance scores</button>}
        <button className={tab === "steps" || (turn.mode !== "crag" && tab === "scores") ? "on" : ""} onClick={() => setTab("steps")}>Step log</button>
        <button className={tab === "flow" ? "on" : ""} onClick={() => setTab("flow")}>Flow diagram</button>
      </div>

      {tab === "scores" && turn.mode === "crag" && (
        <div>
          {evals.map((ev, i) => (
            <div key={i} className="attempt">
              <div className="attempt-head">
                <span>Attempt {i + 1}</span>
                <code>{turn.steps.filter((s) => s.node === "retrieve")[i]?.data?.query}</code>
                <span className={`chip act-${ev.data.action.toLowerCase()}`}>{ev.data.action}</span>
              </div>
              <div className="legend">
                <span><i className="sw lo" />below {ev.data.lower} = irrelevant</span>
                <span><i className="sw mid" />in between = ambiguous</span>
                <span><i className="sw hi" />{ev.data.upper}+ = relevant</span>
              </div>
              {ev.data.docs.map((d) => <DocCard key={d.id} doc={d} upper={ev.data.upper} lower={ev.data.lower} compact />)}
              {!ev.data.docs.length && <div className="muted">No documents in the knowledge base.</div>}
            </div>
          ))}
        </div>
      )}

      {(tab === "steps" || (turn.mode !== "crag" && tab === "scores")) && (
        <ol className="steplog">
          {turn.steps.map((s, i) => (
            <li key={i} className={`n-${s.node}`}>
              <div className="sl-head"><b>{s.title}</b><span>{s.ms < 1000 ? `${Math.round(s.ms)} ms` : `${(s.ms / 1000).toFixed(1)} s`}</span></div>
              <div className="sl-sum">{s.summary}</div>
              {s.node === "web_search" && s.data?.docs?.length > 0 && (
                <div className="sl-docs">{s.data.docs.map((d) => <DocCard key={d.id} doc={d} showScore={false} compact />)}</div>
              )}
            </li>
          ))}
        </ol>
      )}

      {tab === "flow" && (
        <div className="flow-wrap">
          <Pipeline path={r?.path || turn.steps.map((s) => s.node)} action={r?.action} mode={turn.mode} />
        </div>
      )}
    </div>
  );
}

function Turn({ turn }) {
  const [src, setSrc] = useState(null);
  const [showDetails, setShowDetails] = useState(false);
  const r = turn.result;
  return (
    <div className="turn">
      <div className="q-row">
        <div className="q-bubble">{turn.question}</div>
      </div>
      <div className="a-row">
        <div className={`avatar ${turn.mode}`}>{turn.mode === "crag" ? "C" : "R"}</div>
        <div className="a-body">
          <div className="a-meta">
            <span className="who">{turn.mode === "crag" ? "CRAG" : "Traditional RAG"}</span>
            <Stepper steps={turn.steps} active={turn.active} running={turn.running} />
          </div>

          {turn.error && <div className="error">{turn.error}</div>}

          {r && (
            <>
              <div className="badges">
                <RouteBadge route={r.route} />
                <ActionBadge action={r.action} />
                {r.confidence != null && <span className="chip plain">confidence {Math.round(r.confidence * 100)}%</span>}
                {r.corrections?.length > 0 && <span className="chip corr">self-corrected</span>}
              </div>
              <AnswerText text={r.answer} onCite={(n) => setSrc(src === n ? null : n)} />
              {r.rewrites?.length > 0 && (
                <div className="rewrites">
                  {r.rewrites.map((rw, i) => (
                    <div key={i}><span>{rw.purpose === "web" ? "searched web for" : "rewrote query to"}</span>“{rw.query}”</div>
                  ))}
                </div>
              )}
              {r.sources?.length > 0 && (
                <div className="src-chips">
                  {r.sources.map((s) => (
                    <button key={s.n} className={`src-chip ${s.origin} ${src === s.n ? "on" : ""}`} onClick={() => setSrc(src === s.n ? null : s.n)}>
                      <b>{s.n}</b>{s.origin === "web" ? (() => { try { return new URL(s.source).hostname.replace("www.", ""); } catch { return "web"; } })() : s.source}
                    </button>
                  ))}
                </div>
              )}
              {src != null && r.sources.find((s) => s.n === src) && (
                <DocCard doc={r.sources.find((s) => s.n === src)} n={src} showScore={false} />
              )}
              <div className="a-foot">
                <Metrics m={r.metrics} />
                <button className="link" onClick={() => setShowDetails(!showDetails)}>
                  {showDetails ? "Hide" : "Show"} how it answered
                </button>
              </div>
              {showDetails && <Details turn={turn} />}
            </>
          )}
          {!r && !turn.error && <div className="skeleton"><span /><span /><span /></div>}
        </div>
      </div>
    </div>
  );
}

export default function ChatPage({ turns, setTurns, warning, goTo }) {
  const [q, setQ] = useState("");
  const [mode, setMode] = useState("crag");
  const abortRef = useRef(null);
  const endRef = useRef(null);
  const running = turns.some((t) => t.running);

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" }); }, [turns.length, turns.at(-1)?.result]);

  function patch(id, fn) {
    setTurns((ts) => ts.map((t) => (t.id === id ? { ...t, ...fn(t) } : t)));
  }

  async function ask(text) {
    const question = (text ?? q).trim();
    if (!question || running) return;
    setQ("");
    const id = Date.now();
    setTurns((ts) => [...ts, { id, question, mode, steps: [], active: "query", running: true, result: null, error: "" }]);
    abortRef.current = new AbortController();
    try {
      await streamQuery(question, mode, (ev) => {
        if (ev.type === "start") patch(id, () => ({ active: ev.node }));
        else if (ev.type === "step") patch(id, (t) => ({ steps: [...t.steps, ev], active: ev.node }));
        else if (ev.type === "result") patch(id, () => ({ result: ev, active: "final" }));
        else if (ev.type === "error") patch(id, () => ({ error: ev.message }));
      }, abortRef.current.signal);
    } catch (e) {
      patch(id, () => ({ error: e.name === "AbortError" ? "Stopped." : e.message }));
    } finally {
      patch(id, () => ({ running: false }));
    }
  }

  return (
    <div className="chat">
      <div className="chat-scroll">
        {warning && (
          <div className="banner">
            <span>{warning}</span>
            <button className="link" onClick={() => goTo()}>Fix this →</button>
          </div>
        )}
        {turns.length === 0 ? (
          <div className="hero">
            <h1>Ask anything.<br /><span>CRAG checks its sources before it answers.</span></h1>
            <p>Every answer is graded for relevance. When your documents don't cover it, are outdated, or are
              only loosely related, CRAG rewrites the query and searches the web instead.</p>
            <div className="ex-grid">
              {EXAMPLES.map(([cat, ex, what]) => (
                <button key={ex} className="ex-card" onClick={() => ask(ex)}>
                  <span className="ex-cat">{cat}</span>
                  <span className="ex-q">{ex}</span>
                  <span className="ex-what">{what}</span>
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className="thread">
            {turns.map((t) => <Turn key={t.id} turn={t} />)}
            <div ref={endRef} />
          </div>
        )}
      </div>

      <form className="composer" onSubmit={(e) => { e.preventDefault(); ask(); }}>
        <div className="composer-box">
          <textarea value={q} rows={1} placeholder="Ask a question…"
            onChange={(e) => { setQ(e.target.value); e.target.style.height = "auto"; e.target.style.height = Math.min(e.target.scrollHeight, 160) + "px"; }}
            onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); ask(); } }} />
          <div className="composer-bar">
            <div className="seg" title="Which pipeline answers">
              <button type="button" className={mode === "crag" ? "on" : ""} onClick={() => setMode("crag")}>CRAG</button>
              <button type="button" className={mode === "baseline" ? "on" : ""} onClick={() => setMode("baseline")}>Traditional RAG</button>
            </div>
            {turns.length > 0 && !running && <button type="button" className="link muted" onClick={() => setTurns([])}>Clear chat</button>}
            {running ? (
              <button type="button" className="send stop" onClick={() => abortRef.current?.abort()} title="Stop"><Icon name="stop" /></button>
            ) : (
              <button className="send" disabled={!q.trim()} title="Send (Enter)"><Icon name="send" /></button>
            )}
          </div>
        </div>
      </form>
    </div>
  );
}
