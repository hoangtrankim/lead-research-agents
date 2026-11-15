import type { Agent } from "@/lib/api";

const NODES: { id: Agent; label: string; role: string; x: number }[] = [
  { id: "researcher", label: "Researcher", role: "Reads the website", x: 20 },
  { id: "writer", label: "Writer", role: "Drafts the email", x: 220 },
  { id: "reviewer", label: "Reviewer", role: "Scores and critiques", x: 420 },
];

type Props = { active: Agent | null; done: Set<Agent>; looping: boolean; finished: boolean };

/** The LangGraph workflow drawn as a diagram, with the running agent highlighted. */
export default function GraphView({ active, done, looping, finished }: Props) {
  return (
    <svg viewBox="0 0 640 150" className="graph" role="img" aria-label="Agent workflow: researcher, writer, reviewer, with a revision loop from reviewer back to writer">
      <defs>
        <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
          <path d="M0,0 L10,5 L0,10 z" className="arrowhead" />
        </marker>
      </defs>
      <line x1="180" y1="62" x2="216" y2="62" className="edge" markerEnd="url(#arrow)" />
      <line x1="380" y1="62" x2="416" y2="62" className="edge" markerEnd="url(#arrow)" />
      <line x1="580" y1="62" x2="612" y2="62" className="edge" markerEnd="url(#arrow)" />
      <circle cx="624" cy="62" r="8" className={`end ${finished ? "on" : ""}`} />
      <path d="M500,92 C500,138 300,138 300,96" className={`edge loop ${looping ? "on" : ""}`} markerEnd="url(#arrow)" />
      <text x="400" y="143" textAnchor="middle" className="edge-label">
        needs revision
      </text>
      {NODES.map((n) => (
        <g key={n.id} className={`node ${active === n.id ? "active" : ""} ${done.has(n.id) ? "done" : ""}`}>
          <rect x={n.x} y="32" width="160" height="60" rx="12" />
          <text x={n.x + 80} y="58" textAnchor="middle" className="node-label">
            {n.label}
          </text>
          <text x={n.x + 80} y="76" textAnchor="middle" className="node-role">
            {n.role}
          </text>
        </g>
      ))}
    </svg>
  );
}
