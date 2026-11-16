import { useEffect, useState } from "react";
import { api } from "./api";
import Icon from "./components/icons";
import ChatPage from "./pages/ChatPage";
import ComparePage from "./pages/ComparePage";
import EvalPage from "./pages/EvalPage";
import KnowledgePage from "./pages/KnowledgePage";
import SettingsPage from "./pages/SettingsPage";
import StatusPage from "./pages/StatusPage";

const NAV = [
  ["chat", "Chat", "chat"],
  ["compare", "CRAG vs RAG", "compare"],
  ["kb", "Documents", "docs"],
  ["eval", "Evaluation", "eval"],
  ["settings", "Settings", "settings"],
  ["status", "System check", "status"],
];

export default function App() {
  const [tab, setTab] = useState("chat");
  const [health, setHealth] = useState(null);
  const [down, setDown] = useState("");
  const [diag, setDiag] = useState(null);
  const [turns, setTurns] = useState([]);

  const refresh = () => api.health().then((h) => { setHealth(h); setDown(""); }).catch((e) => setDown(e.message));
  useEffect(() => {
    refresh();
    api.diagnostics().then(setDiag).catch(() => {});
  }, []);

  const failing = diag?.checks?.filter((c) => !c.ok && c.name !== "Web search") || [];
  let warning = "";
  if (down) warning = "The backend is not reachable, so nothing will work until it is started.";
  else if (failing.length) warning = `${failing.map((c) => c.name).join(" and ")} not working: ${failing[0].error}`;
  else if (health && health.chunks === 0) warning = "Your knowledge base is empty. Add documents or load the samples on the Documents page.";

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="logo"><svg viewBox="0 0 32 32" width="18" height="18"><path d="M7 16h6l3-7 3 14 2-7h4" stroke="currentColor" strokeWidth="2.6" fill="none" strokeLinecap="round" strokeLinejoin="round" /></svg></div>
          <div><b>CRAG</b><span>Self-corrective RAG</span></div>
        </div>
        <nav>
          {NAV.map(([k, label, icon]) => (
            <button key={k} className={tab === k ? "on" : ""} onClick={() => setTab(k)}>
              <Icon name={icon} size={17} />{label}
              {k === "status" && (down || failing.length > 0) && <span className="dot-bad" />}
            </button>
          ))}
        </nav>
        <div className="side-status">
          <div className={`ss-row ${down ? "bad" : ""}`}>
            <span className="ss-k">Backend</span><span className="ss-v">{down ? "offline" : health ? "online" : "…"}</span>
          </div>
          {health && (
            <>
              <div className={`ss-row ${health.llm.mock ? "warn" : ""}`}>
                <span className="ss-k">LLM</span>
                <span className="ss-v" title={health.llm.model}>{health.llm.mock ? "demo (mock)" : health.llm.model.split("/").pop()}</span>
              </div>
              <div className="ss-row"><span className="ss-k">Embeddings</span><span className="ss-v">{health.embeddings}</span></div>
              <div className={`ss-row ${health.web_search === "none" ? "warn" : ""}`}><span className="ss-k">Web search</span><span className="ss-v">{health.web_search}</span></div>
              <div className="ss-row"><span className="ss-k">Knowledge</span><span className="ss-v">{health.documents} docs · {health.chunks} chunks</span></div>
            </>
          )}
        </div>
      </aside>

      <main className={tab === "chat" ? "main chat-main" : "main"}>
        {tab === "chat" && <ChatPage turns={turns} setTurns={setTurns} warning={warning} goTo={(t) => setTab(failing.length || down ? "status" : "kb")} />}
        {tab === "compare" && <ComparePage />}
        {tab === "kb" && <KnowledgePage onChange={refresh} />}
        {tab === "eval" && <EvalPage />}
        {tab === "settings" && <SettingsPage onChange={refresh} />}
        {tab === "status" && <StatusPage onResult={(d, e) => { setDiag(d); refresh(); }} />}
      </main>
    </div>
  );
}
