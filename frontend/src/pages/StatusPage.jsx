import { useEffect, useState } from "react";
import { api } from "../api";
import Icon from "../components/icons";
import { Spinner } from "../components/ui";

export default function StatusPage({ onResult }) {
  const [data, setData] = useState(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  async function run() {
    setBusy(true); setErr("");
    try { const d = await api.diagnostics(); setData(d); onResult?.(d); }
    catch (e) { setErr(e.message); setData(null); onResult?.(null, e.message); }
    finally { setBusy(false); }
  }
  useEffect(() => { run(); }, []);

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h2>System check</h2>
          <p className="lead">Each component is tested with a real call. If something is red, the hint says how to fix it.</p>
        </div>
        <button className="btn" onClick={run} disabled={busy}><Icon name="refresh" size={14} /> Re-run</button>
      </div>

      {err && (
        <div className="check bad">
          <div className="check-icon"><Icon name="x" /></div>
          <div>
            <b>Backend</b>
            <div className="check-err">{err}</div>
            <div className="check-hint">In a terminal: <code>cd backend</code> → activate the venv → <code>uvicorn app.main:app --port 8000</code>. Keep that terminal open.</div>
          </div>
        </div>
      )}
      {busy && !data && <div className="muted pad"><Spinner /> Testing components… (the first run may take a while to load the embedding model)</div>}

      {data && (
        <div className="checks">
          <div className="check ok">
            <div className="check-icon"><Icon name="check" /></div>
            <div><b>Backend API</b><div className="check-detail">Reachable</div></div>
          </div>
          {data.checks.map((c) => (
            <div key={c.name} className={`check ${c.ok ? "ok" : c.name === "Web search" ? "warn" : "bad"}`}>
              <div className="check-icon"><Icon name={c.ok ? "check" : "x"} /></div>
              <div>
                <b>{c.name}</b> <span className="muted tiny">{c.ms} ms</span>
                {c.ok ? <div className="check-detail">{c.detail}</div> : (
                  <>
                    <div className="check-err">{c.error}</div>
                    <div className="check-hint">{c.hint}</div>
                  </>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
