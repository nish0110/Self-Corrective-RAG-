// Live CRAG flow diagram: nodes light up as the backend streams each step.
const N = {
  query: [210, 28, "Query"],
  retrieve: [210, 88, "Vector search"],
  evaluate: [210, 148, "Relevance evaluator"],
  route: [210, 208, "Router"],
  rewrite: [340, 268, "Query rewrite"],
  web_search: [340, 328, "Web search"],
  refine: [210, 388, "Knowledge refine"],
  generate: [210, 448, "LLM generate"],
  validate: [210, 508, "Answer validation"],
  correct: [64, 508, "Self-correct"],
  final: [210, 568, "Final answer"],
};
const W = 124, H = 34;

const EDGES = [
  ["query", "retrieve"],
  ["retrieve", "evaluate"],
  ["evaluate", "route"],
  ["route", "refine", "CORRECT", "M210 225 L210 371", [218, 300]],
  ["route", "rewrite", "AMBIGUOUS / INCORRECT", "M250 225 L320 251", [350, 243]],
  ["rewrite", "retrieve", "retry", "M402 268 C440 268 440 88 402 88 L272 88", [446, 178]],
  ["rewrite", "web_search"],
  ["web_search", "refine", "", "M318 345 L250 371"],
  ["refine", "generate"],
  ["generate", "validate"],
  ["validate", "final", "PASS"],
  ["validate", "correct", "FAIL", "M148 508 L126 508", [137, 500]],
  ["correct", "generate", "strict", "M64 491 L64 448 L148 448", [52, 470]],
  ["correct", "rewrite", "escalate", "M30 491 L30 300 C30 280 40 268 60 268 L278 268", [24, 380]],
];

function straight(a, b) {
  const [x1, y1] = N[a], [x2, y2] = N[b];
  if (x1 === x2) return `M${x1} ${y1 + H / 2} L${x2} ${y2 - H / 2}`;
  return `M${x1} ${y1 + H / 2} L${x2} ${y2 - H / 2}`;
}

export default function Pipeline({ path = [], active = null, action = null, mode = "crag" }) {
  const visited = new Set(path);
  const used = new Set();
  for (let i = 0; i < path.length - 1; i++) used.add(`${path[i]}>${path[i + 1]}`);
  const hidden = mode === "baseline" ? new Set(["evaluate", "route", "rewrite", "web_search", "refine", "validate", "correct"]) : new Set();
  const edges = mode === "baseline" ? [["query", "retrieve"], ["retrieve", "generate", "", "M210 105 L210 431"], ["generate", "final", "", "M210 465 L210 551"]] : EDGES;
  const bvisited = mode === "baseline" ? new Set(["query", ...path]) : visited;
  if (mode === "baseline") {
    for (let i = 0; i < path.length - 1; i++) used.add(`${path[i]}>${path[i + 1]}`);
    if (path.length) used.add("query>retrieve");
  }

  return (
    <svg viewBox="0 0 470 595" className="pipeline" role="img" aria-label="CRAG pipeline diagram">
      <defs>
        <marker id="arr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
          <path d="M0 0 L10 5 L0 10 z" fill="var(--edge)" />
        </marker>
        <marker id="arrOn" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
          <path d="M0 0 L10 5 L0 10 z" fill="var(--accent)" />
        </marker>
      </defs>
      {edges.map(([a, b, label, d, lp]) => {
        const on = used.has(`${a}>${b}`);
        return (
          <g key={a + b} className={on ? "edge on" : "edge"}>
            <path d={d || straight(a, b)} markerEnd={on ? "url(#arrOn)" : "url(#arr)"} />
            {label && (
              <text x={(lp || [])[0] ?? (N[a][0] + 8)} y={(lp || [])[1] ?? ((N[a][1] + N[b][1]) / 2 + 4)}
                className="edge-label" textAnchor={lp ? "middle" : "start"}>{label}</text>
            )}
          </g>
        );
      })}
      {Object.entries(N).map(([k, [x, y, label]]) => {
        if (hidden.has(k)) return null;
        const cls = ["node", bvisited.has(k) ? "visited" : "", active === k ? "active" : "",
          k === "route" && action ? `act-${action.toLowerCase()}` : ""].join(" ");
        return (
          <g key={k} className={cls} transform={`translate(${x - W / 2},${y - H / 2})`}>
            <rect width={W} height={H} rx={9} />
            <text x={W / 2} y={H / 2 + 4} textAnchor="middle">
              {k === "route" && action ? `Router: ${action}` : label}
            </text>
          </g>
        );
      })}
    </svg>
  );
}
