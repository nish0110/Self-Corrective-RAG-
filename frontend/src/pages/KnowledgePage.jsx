import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import Icon from "../components/icons";
import { Spinner } from "../components/ui";

const ACCEPT = ".pdf,.txt,.md,.markdown,.docx,.csv,.html,.htm";

export default function KnowledgePage({ onChange }) {
  const [docs, setDocs] = useState([]);
  const [chunks, setChunks] = useState(0);
  const [busy, setBusy] = useState("");
  const [log, setLog] = useState([]);   // per-file upload results
  const [err, setErr] = useState("");
  const [drag, setDrag] = useState(false);
  const input = useRef(null);

  async function refresh() {
    try {
      const r = await api.documents();
      setDocs(r.documents); setChunks(r.chunks); setErr("");
    } catch (e) { setErr(e.message); }
    onChange?.();
  }
  useEffect(() => { refresh(); }, []);

  async function wrap(label, fn) {
    setBusy(label); setErr("");
    try { await fn(); } catch (e) { setErr(e.message); }
    finally { setBusy(""); refresh(); }
  }

  const upload = (files) => {
    if (!files?.length) return;
    const list = [...files];
    setLog(list.map((f) => ({ source: f.name, pending: true })));
    return wrap(`Reading and embedding ${list.length} file${list.length > 1 ? "s" : ""}…`, async () => {
      try {
        const r = await api.upload(list);
        setLog(r.results);
      } catch (e) {
        setLog(list.map((f) => ({ source: f.name, error: e.message })));
        throw e;
      }
    });
  };

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h2>Documents</h2>
          <p className="lead">Your local knowledge base. Files are split into chunks, embedded and stored in ChromaDB, and CRAG searches these first.</p>
        </div>
        <div className="row gap0">
          <button className="btn" onClick={() => wrap("Loading samples…", async () => setLog((await api.loadSamples()).results))} disabled={!!busy}>
            <Icon name="plus" size={14} /> Load sample documents
          </button>
          <button className="btn danger" disabled={!!busy || !docs.length}
            onClick={() => confirm("Delete every document from the knowledge base?") && wrap("Clearing…", api.resetDocs)}>
            <Icon name="trash" size={14} /> Clear all
          </button>
        </div>
      </div>

      <div className={`drop ${drag ? "drag" : ""} ${busy ? "busy" : ""}`}
        onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => { e.preventDefault(); setDrag(false); !busy && upload(e.dataTransfer.files); }}
        onClick={() => !busy && input.current?.click()}>
        <input ref={input} type="file" multiple hidden accept={ACCEPT}
          onChange={(e) => { upload(e.target.files); e.target.value = ""; }} />
        <div className="drop-icon">{busy ? <Spinner /> : <Icon name="upload" size={22} />}</div>
        <b>{busy || "Drop files here or click to browse"}</b>
        <span className="muted">PDF, DOCX, TXT, MD, CSV, HTML. Re-uploading a file replaces it.</span>
      </div>

      {err && <div className="error">{err}</div>}

      {log.length > 0 && (
        <div className="upload-log">
          {log.map((r, i) => (
            <div key={i} className={`ul-row ${r.pending ? "pending" : r.error ? "bad" : "ok"}`}>
              <span className="ul-icon">{r.pending ? <Spinner /> : <Icon name={r.error ? "x" : "check"} size={14} />}</span>
              <span className="mono">{r.source}</span>
              <span className="ul-msg">{r.pending ? "processing…" : r.error ? r.error : `${r.chunks} chunks added`}</span>
            </div>
          ))}
        </div>
      )}

      <div className="panel flush">
        <table className="table">
          <thead><tr><th>Document</th><th>File</th><th className="num">Chunks</th><th /></tr></thead>
          <tbody>
            {docs.map((d) => (
              <tr key={d.source}>
                <td>{d.title}</td>
                <td className="mono muted">{d.source}</td>
                <td className="num">{d.chunks}</td>
                <td className="num"><button className="icon-btn" title="Delete" disabled={!!busy}
                  onClick={() => wrap("Deleting…", () => api.deleteDoc(d.source))}><Icon name="trash" size={15} /></button></td>
              </tr>
            ))}
            {!docs.length && <tr><td colSpan={4} className="empty">No documents yet. Upload files or load the samples.</td></tr>}
          </tbody>
          {docs.length > 0 && <tfoot><tr><td>{docs.length} documents</td><td /><td className="num">{chunks}</td><td /></tr></tfoot>}
        </table>
      </div>
    </div>
  );
}
