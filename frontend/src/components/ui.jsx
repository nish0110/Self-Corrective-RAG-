import { Fragment, useState } from "react";
import Icon from "./icons";

export const ROUTE_TEXT = {
  local: "From your documents",
  hybrid: "Documents + web",
  web: "From web search",
  none: "No usable source",
};

export const NODE_LABEL = {
  query: "Understand",
  retrieve: "Retrieve",
  evaluate: "Grade docs",
  route: "Route",
  rewrite: "Rewrite query",
  web_search: "Web search",
  refine: "Refine",
  generate: "Generate",
  validate: "Validate",
  correct: "Self-correct",
};

export function RouteBadge({ route }) {
  if (!route) return null;
  return <span className={`chip route-${route}`}><i />{ROUTE_TEXT[route] || route}</span>;
}

export function ActionBadge({ action }) {
  if (!action) return null;
  const t = { CORRECT: "Relevant", AMBIGUOUS: "Partly relevant", INCORRECT: "Irrelevant" }[action];
  return <span className={`chip act-${action.toLowerCase()}`} title={`Evaluator verdict: ${action}`}>Retrieval: {t}</span>;
}

export function ScoreBar({ value, upper, lower }) {
  const v = value ?? 0;
  const cls = upper != null && v >= upper ? "hi" : lower != null && v < lower ? "lo" : "mid";
  return (
    <div className="scorebar">
      <div className={`fill ${cls}`} style={{ width: `${Math.max(2, v * 100)}%` }} />
      {lower != null && <div className="tick" style={{ left: `${lower * 100}%` }} />}
      {upper != null && <div className="tick" style={{ left: `${upper * 100}%` }} />}
    </div>
  );
}

/** Render "[1][2]" citation markers as clickable chips. */
export function AnswerText({ text, onCite }) {
  if (!text) return null;
  const parts = text.split(/(\[\d+\])/g);
  return (
    <div className="answer-text">
      {parts.map((p, i) => {
        const m = p.match(/^\[(\d+)\]$/);
        if (m) return <button key={i} className="cite" onClick={() => onCite?.(+m[1])}>{m[1]}</button>;
        return <Fragment key={i}>{p.replace(/\*\*(.+?)\*\*/g, "$1")}</Fragment>;
      })}
    </div>
  );
}

export function DocCard({ doc, n, upper, lower, showScore = true, compact }) {
  const [open, setOpen] = useState(false);
  const isWeb = doc.origin === "web";
  return (
    <div className={`doc ${doc.label || ""} ${compact ? "compact" : ""}`}>
      <div className="doc-head">
        {n != null && <span className="doc-n">{n}</span>}
        <span className={`origin ${doc.origin}`}>{isWeb ? "WEB" : "DOC"}</span>
        {isWeb ? (
          <a href={doc.source} target="_blank" rel="noreferrer" className="doc-title">{doc.title || doc.source} <Icon name="ext" size={12} /></a>
        ) : (
          <span className="doc-title">{doc.title || doc.source}</span>
        )}
        {showScore && doc.relevance != null && <span className={`score-num ${doc.label}`}>{doc.relevance.toFixed(2)}</span>}
      </div>
      {showScore && doc.relevance != null && <ScoreBar value={doc.relevance} upper={upper} lower={lower} />}
      {doc.reason && <div className="doc-reason">{doc.reason}</div>}
      <div className={`doc-text ${open ? "open" : ""}`} onClick={() => setOpen(!open)} title="click to expand">{doc.text}</div>
      {!isWeb && <div className="doc-src">{doc.source}{doc.metadata?.page > 1 ? ` · page ${doc.metadata.page}` : ""}</div>}
    </div>
  );
}

export function Metrics({ m }) {
  if (!m) return null;
  return (
    <div className="metrics">
      <span>{(m.latency_ms / 1000).toFixed(1)}s</span>
      <span>{m.llm_calls} LLM calls</span>
      <span>{m.total_tokens.toLocaleString()} tokens</span>
      <span>{m.retrieval_attempts} retrieval{m.retrieval_attempts === 1 ? "" : "s"}</span>
      <span>{m.web_searches} web search{m.web_searches === 1 ? "" : "es"}</span>
    </div>
  );
}

export function Spinner() {
  return <span className="spinner" aria-label="loading" />;
}
