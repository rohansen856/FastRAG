import type { PipelineStageTrace, CacheStatus } from "@/lib/types";

export function PipelineDiagram({
  stages,
  cacheStatus,
  outcome,
}: {
  stages: PipelineStageTrace[];
  cacheStatus: CacheStatus;
  outcome: string;
}) {
  const blocked = stages.find((stage) => stage.status === "blocked");
  const cacheHit = cacheStatus !== "miss";

  return (
    <div className="overflow-x-auto">
      <svg viewBox="0 0 720 120" className="w-full min-w-[560px] h-auto text-foreground/80">
        <defs>
          <marker id="arrow" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">
            <path d="M0,0 L6,3 L0,6 Z" fill="currentColor" />
          </marker>
        </defs>
        {[
          { x: 20, label: "Guard" },
          { x: 110, label: "Index" },
          { x: 200, label: "Cache" },
          { x: 290, label: "Embed" },
          { x: 380, label: "Retrieve" },
          { x: 470, label: "Rerank" },
          { x: 560, label: "CRAG" },
          { x: 650, label: "Generate" },
        ].map((node, index, nodes) => (
          <g key={node.label}>
            <rect
              x={node.x}
              y="40"
              width="70"
              height="36"
              rx="8"
              fill="none"
              stroke="currentColor"
              strokeOpacity="0.25"
            />
            <text x={node.x + 35} y="62" textAnchor="middle" fontSize="11" fill="currentColor">
              {node.label}
            </text>
            {index < nodes.length - 1 && (
              <line
                x1={node.x + 70}
                y1="58"
                x2={nodes[index + 1].x}
                y2="58"
                stroke="currentColor"
                strokeOpacity="0.2"
                markerEnd="url(#arrow)"
              />
            )}
          </g>
        ))}
        {cacheHit && (
          <text x="360" y="20" textAnchor="middle" fontSize="11" fill="currentColor">
            Cache {cacheStatus} — downstream skipped
          </text>
        )}
        {blocked && (
          <text x="360" y="108" textAnchor="middle" fontSize="11" fill="#be123c">
            Blocked at {blocked.label.toLowerCase()}
          </text>
        )}
        {outcome === "no_answer" && !blocked && (
          <text x="360" y="108" textAnchor="middle" fontSize="11" fill="currentColor" opacity="0.7">
            Abstained before generation
          </text>
        )}
      </svg>
    </div>
  );
}
