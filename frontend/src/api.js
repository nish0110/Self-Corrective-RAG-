const BASE = import.meta.env.VITE_API_URL || "";

async function req(path, opts = {}) {
  let r;
  try {
    r = await fetch(BASE + path, opts);
  } catch {
    throw new Error("Cannot reach the backend. Is it running? Start it with: uvicorn app.main:app --port 8000");
  }
  if (!r.ok) {
    let msg = `${r.status} ${r.statusText}`;
    try {
      const body = await r.json();
      if (body.detail) msg = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch { /* not JSON */ }
    if (r.status === 502 || r.status === 504 || (r.status === 500 && msg.startsWith("500")))
      msg = "Backend is not responding (the frontend proxy could not reach port 8000). Start the backend and retry.";
    throw new Error(msg);
  }
  return r.json();
}

const json = (method, body) => ({
  method,
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

export const api = {
  health: () => req("/api/health"),
  diagnostics: () => req("/api/diagnostics"),
  config: () => req("/api/config"),
  saveConfig: (c) => req("/api/config", json("PUT", c)),
  documents: () => req("/api/documents"),
  loadSamples: () => req("/api/documents/load-samples", { method: "POST" }),
  deleteDoc: (s) => req(`/api/documents/${encodeURIComponent(s)}`, { method: "DELETE" }),
  resetDocs: () => req("/api/documents", { method: "DELETE" }),
  upload: (files) => {
    const fd = new FormData();
    [...files].forEach((f) => fd.append("files", f, f.name));
    return req("/api/documents/upload", { method: "POST", body: fd });
  },
  query: (query, mode = "crag") => req("/api/query", json("POST", { query, mode })),
  runEval: (limit, category) => {
    const p = new URLSearchParams();
    if (limit) p.set("limit", limit);
    if (category) p.set("category", category);
    return req(`/api/eval/run?${p}`, { method: "POST" });
  },
  evalStatus: () => req("/api/eval/status"),
  evalResults: () => req("/api/eval/results"),
};

/** POST + Server-Sent Events: calls onEvent for every pipeline event. */
export async function streamQuery(query, mode, onEvent, signal) {
  let r;
  try {
    r = await fetch(BASE + "/api/query/stream", { ...json("POST", { query, mode }), signal });
  } catch (e) {
    if (e.name === "AbortError") throw e;
    throw new Error("Cannot reach the backend. Is it running on port 8000?");
  }
  if (!r.ok) {
    let msg = `HTTP ${r.status}`;
    try { msg = (await r.json()).detail || msg; } catch { /* ignore */ }
    throw new Error(msg);
  }
  const reader = r.body.getReader();
  const dec = new TextDecoder();
  let buf = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    let i;
    while ((i = buf.indexOf("\n\n")) >= 0) {
      const chunk = buf.slice(0, i);
      buf = buf.slice(i + 2);
      for (const line of chunk.split("\n")) {
        if (line.startsWith("data: ")) onEvent(JSON.parse(line.slice(6)));
      }
    }
  }
}
