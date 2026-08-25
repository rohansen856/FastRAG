import type { PipelineStageTrace, CacheStatus, Outcome } from "@/lib/types";

type NodeKind = "stage" | "decision" | "terminal";

interface FlowNode {
  id: string;
  label: string;
  kind: NodeKind;
}

/** Canonical pipeline graph - not a duplicate of the timeline list. */
const GRAPH: FlowNode[] = [
  { id: "stt", label: "Voice in", kind: "stage" },
  { id: "guardrail", label: "Text guard", kind: "stage" },
  { id: "index_registry", label: "Index", kind: "stage" },
  { id: "exact_cache", label: "Exact hit?", kind: "decision" },
  { id: "embedding", label: "Embed", kind: "stage" },
  { id: "vector_guardrail", label: "Vector guard", kind: "stage" },
  { id: "semantic_cache", label: "Semantic hit?", kind: "decision" },
  { id: "retrieval", label: "Retrieve", kind: "stage" },
  { id: "rerank", label: "Rerank", kind: "stage" },
  { id: "crag", label: "CRAG", kind: "stage" },
  { id: "generation", label: "Generate", kind: "stage" },
];

function stageMap(stages: PipelineStageTrace[]): Map<string, PipelineStageTrace> {
  return new Map(stages.map((stage) => [stage.id, stage]));
}

function pathTaken(stages: PipelineStageTrace[], cacheStatus: CacheStatus): Set<string> {
  const byId = stageMap(stages);
  const active = new Set<string>();

  for (const node of GRAPH) {
    if (node.id === "stt" && !byId.has("stt")) continue;

    const stage = byId.get(node.id);
    if (!stage) continue;

    active.add(node.id);

    if (stage.status === "blocked") break;

    if (node.id === "exact_cache" && cacheStatus === "exact") break;
    if (node.id === "semantic_cache" && cacheStatus === "semantic") break;

    if (stage.status === "skipped") break;
  }

  return active;
}

function nodeClass(active: boolean, stage: PipelineStageTrace | undefined): string {
  if (stage?.status === "blocked") {
    return "border-rose-500/50 bg-rose-500/10 text-rose-800";
  }
  if (active) {
    return "border-emerald-500/45 bg-emerald-500/10 text-emerald-900";
  }
  return "border-foreground/10 bg-foreground/[0.02] text-muted-foreground";
}

export function PipelineDiagram({
  stages,
  cacheStatus,
  outcome,
}: {
  stages: PipelineStageTrace[];
  cacheStatus: CacheStatus;
  outcome: Outcome;
}) {
  const byId = stageMap(stages);
  const active = pathTaken(stages, cacheStatus);
  const nodes = GRAPH.filter((node) => node.id !== "stt" || byId.has("stt"));

  const pathLabel =
    cacheStatus === "exact"
      ? "Exact cache short-circuit"
      : cacheStatus === "semantic"
        ? "Semantic cache short-circuit"
        : outcome === "refused"
          ? "Guardrail refusal"
          : outcome === "no_answer"
            ? "Abstained before answer"
            : "Full retrieval path";

  return (
    <div className="space-y-4">
      <p className="rounded-lg border border-foreground/10 bg-foreground/[0.02] px-3 py-2 text-xs leading-relaxed">
        <span className="font-medium text-foreground">Path taken: </span>
        <span className="text-muted-foreground">{pathLabel}</span>
      </p>

      <div className="flex flex-wrap items-center gap-x-1.5 gap-y-3 py-1">
          {nodes.map((node, index) => {
            const stage = byId.get(node.id);
            const isActive = active.has(node.id);
            const isDecision = node.kind === "decision";

            return (
              <div key={node.id} className="flex items-center gap-1.5">
                {isDecision ? (
                  <div
                    className={`flex h-11 w-11 shrink-0 items-center justify-center ${nodeClass(isActive, stage)} border rotate-45 rounded-sm`}
                    title={stage?.detail ?? undefined}
                  >
                    <span className="-rotate-45 text-[9px] font-mono leading-none text-center px-0.5">
                      {node.label}
                    </span>
                  </div>
                ) : (
                  <div
                    className={`shrink-0 rounded-lg border px-2.5 py-2 text-center ${nodeClass(isActive, stage)}`}
                    title={stage?.detail ?? undefined}
                  >
                    <span className="block text-[10px] font-mono leading-tight whitespace-nowrap">
                      {node.label}
                    </span>
                  </div>
                )}
                {index < nodes.length - 1 && (
                  <span
                    className={`text-sm shrink-0 ${isActive && active.has(nodes[index + 1].id) ? "text-emerald-600" : "text-foreground/20"}`}
                    aria-hidden
                  >
                    →
                  </span>
                )}
              </div>
            );
          })}
          {(outcome === "no_answer" || outcome === "refused") && (
            <>
              <span className="text-foreground/20">→</span>
              <div
                className={`rounded-lg border px-2.5 py-2 text-[10px] font-mono ${
                  outcome === "refused"
                    ? "border-rose-500/45 bg-rose-500/10 text-rose-800"
                    : "border-amber-500/45 bg-amber-500/10 text-amber-900"
                }`}
              >
                {outcome === "refused" ? "Refused" : "No answer"}
              </div>
            </>
          )}
          {outcome === "answered" && cacheStatus === "miss" && (
            <>
              <span className="text-foreground/20">→</span>
              <div className="rounded-lg border border-emerald-500/45 bg-emerald-500/10 px-2.5 py-2 text-[10px] font-mono text-emerald-900">
                Answered
              </div>
            </>
          )}
          {cacheStatus !== "miss" && (
            <>
              <span className="text-emerald-600 shrink-0">→</span>
              <div className="shrink-0 rounded-lg border border-emerald-500/45 bg-emerald-500/10 px-2.5 py-2 text-[10px] font-mono text-emerald-900">
                Cached answer
              </div>
            </>
          )}
      </div>

      <div className="flex flex-wrap gap-3 text-[10px] font-mono text-muted-foreground">
        <span className="inline-flex items-center gap-1.5">
          <span className="h-2 w-2 rounded-full bg-emerald-500" />
          On path
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="h-2 w-2 rounded-full bg-foreground/20" />
          Not reached
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="h-2 w-2 rotate-45 rounded-sm bg-foreground/15" />
          Cache gate
        </span>
      </div>
    </div>
  );
}
