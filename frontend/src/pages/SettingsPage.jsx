import { useEffect, useState } from "react";
import { api } from "../api";

function Slider({ label, hint, k, cfg, set, min = 0, max = 1, step = 0.05 }) {
  return (
    <label className="field">
      <div className="field-top"><span>{label}</span><b className="mono">{cfg[k]}</b></div>
      <input type="range" min={min} max={max} step={step} value={cfg[k]}
        onChange={(e) => set({ ...cfg, [k]: +e.target.value })} />
      {hint && <small className="muted">{hint}</small>}
    </label>
  );
}

function Toggle({ label, hint, k, cfg, set }) {
  return (
    <label className="field toggle">
      <input type="checkbox" checked={!!cfg[k]} onChange={(e) => set({ ...cfg, [k]: e.target.checked })} />
      <div><span>{label}</span>{hint && <small className="muted">{hint}</small>}</div>
    </label>
  );
}

export default function SettingsPage({ onChange }) {
  const [cfg, setCfg] = useState(null);
  const [saved, setSaved] = useState("");

  const [err, setErr] = useState("");
  useEffect(() => { api.config().then(setCfg).catch((e) => setErr(e.message)); }, []);
  if (err) return <div className="page"><div className="error">{err}</div></div>;
  if (!cfg) return null;

  async function save() {
    const keys = ["top_k", "upper_threshold", "lower_threshold", "max_rewrites", "enable_refinement",
      "strip_threshold", "web_search_provider", "web_results", "enable_validation",
      "max_validation_retries", "validation_threshold", "evaluator_backend"];
    const body = Object.fromEntries(keys.map((k) => [k, cfg[k]]));
    setCfg(await api.saveConfig(body));
    setSaved("Saved — applies to the next query.");
    onChange?.();
    setTimeout(() => setSaved(""), 2500);
  }

  return (
    <div className="page settings">
      <div className="page-head"><div><h2>Settings</h2>
      <p className="lead">Runtime settings (they reset when the server restarts — put permanent values in <code>backend/.env</code>).
        Model: <code>{cfg.llm_provider}:{cfg.llm_model}</code>, embeddings <code>{cfg.embedding_model}</code>.</p></div></div>

      <div className="settings-grid">
        <div className="panel">
          <h3>Retrieval evaluator &amp; router</h3>
          <label className="field">
            <div className="field-top"><span>Evaluator backend</span></div>
            <select value={cfg.evaluator_backend} onChange={(e) => setCfg({ ...cfg, evaluator_backend: e.target.value })}>
              <option value="llm">LLM-as-judge (most accurate)</option>
              <option value="cross_encoder">Cross-encoder (local, fast)</option>
              <option value="embedding">Embedding similarity (cheapest)</option>
            </select>
          </label>
          <Slider label="Upper threshold (CORRECT ≥)" k="upper_threshold" cfg={cfg} set={setCfg}
            hint="If any document scores at or above this, answer from local knowledge." />
          <Slider label="Lower threshold (INCORRECT <)" k="lower_threshold" cfg={cfg} set={setCfg}
            hint="If every document scores below this, discard local context and search the web." />
          <Slider label="Top-k documents" k="top_k" cfg={cfg} set={setCfg} min={1} max={10} step={1} />
          <Slider label="Max query rewrites before web fallback" k="max_rewrites" cfg={cfg} set={setCfg} min={0} max={3} step={1} />
        </div>

        <div className="panel">
          <h3>Correction &amp; generation</h3>
          <label className="field">
            <div className="field-top"><span>Web search provider</span></div>
            <select value={cfg.web_search_provider} onChange={(e) => setCfg({ ...cfg, web_search_provider: e.target.value })}>
              <option value="tavily" disabled={!cfg.tavily_key_set}>Tavily {cfg.tavily_key_set ? "" : "(no key set)"}</option>
              <option value="duckduckgo">DuckDuckGo (no key)</option>
              <option value="none">Disabled</option>
            </select>
          </label>
          <Slider label="Web results" k="web_results" cfg={cfg} set={setCfg} min={1} max={8} step={1} />
          <Toggle label="Knowledge refinement" k="enable_refinement" cfg={cfg} set={setCfg}
            hint="Decompose documents into strips and drop irrelevant sentences." />
          <Slider label="Strip relevance threshold" k="strip_threshold" cfg={cfg} set={setCfg} max={0.6} step={0.01} />
          <Toggle label="Answer validation" k="enable_validation" cfg={cfg} set={setCfg}
            hint="Check groundedness; self-correct if the answer is unsupported." />
          <Slider label="Validation pass score" k="validation_threshold" cfg={cfg} set={setCfg} />
          <Slider label="Max self-correction rounds" k="max_validation_retries" cfg={cfg} set={setCfg} min={0} max={3} step={1} />
        </div>
      </div>
      <div className="row gap">
        <button className="btn primary" onClick={save}>Save settings</button>
        {saved && <span className="muted">{saved}</span>}
      </div>
    </div>
  );
}
