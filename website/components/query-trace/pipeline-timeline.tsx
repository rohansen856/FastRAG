import { CheckCircle2, CircleSlash, MinusCircle } from "lucide-react";
import type { PipelineStageTrace, StageStatus } from "@/lib/types";

const STATUS_ICON: Record<StageStatus, typeof CheckCircle2> = {
  ok: CheckCircle2,
  skipped: MinusCircle,
  blocked: CircleSlash,
};

const STATUS_CLASS: Record<StageStatus, string> = {
  ok: "text-emerald-700",
  skipped: "text-muted-foreground",
  blocked: "text-rose-700",
};

export function PipelineTimeline({
  stages,
  generationMs,
  totalMs,
}: {
  stages: PipelineStageTrace[];
  generationMs?: number;
  totalMs?: number;
}) {
  if (!stages.length) return null;

  const retrievalMs = stages
    .filter((stage) =>
      [
        "guardrail",
        "embedding",
        "exact_cache",
        "semantic_cache",
        "retrieval",
        "rerank",
        "crag",
        "vector_guardrail",
      ].includes(stage.id),
    )
    .reduce((sum, stage) => sum + stage.duration_ms, 0);

  return (
    <div>
      <div className="mb-5 grid gap-2 sm:grid-cols-3">
        {totalMs !== undefined && (
          <div className="rounded-lg border border-foreground/10 bg-foreground/[0.02] px-3 py-2">
            <p className="text-[10px] font-mono uppercase tracking-widest text-muted-foreground">
              Total
            </p>
            <p className="font-mono text-sm">{totalMs.toFixed(0)} ms</p>
          </div>
        )}
        <div className="rounded-lg border border-foreground/10 bg-foreground/[0.02] px-3 py-2">
          <p className="text-[10px] font-mono uppercase tracking-widest text-muted-foreground">
            Retrieval pipeline
          </p>
          <p className="font-mono text-sm">{retrievalMs.toFixed(0)} ms</p>
        </div>
        {generationMs !== undefined && generationMs > 0 && (
          <div className="rounded-lg border border-foreground/10 bg-foreground/[0.02] px-3 py-2">
            <p className="text-[10px] font-mono uppercase tracking-widest text-muted-foreground">
              Generation
            </p>
            <p className="font-mono text-sm">{generationMs.toFixed(0)} ms</p>
          </div>
        )}
      </div>

      <ol className="relative space-y-0">
        {stages.map((stage, index) => {
          const Icon = STATUS_ICON[stage.status];
          const isLast = index === stages.length - 1;
          return (
            <li key={`${stage.id}-${index}`} className="relative flex gap-4 pb-5 last:pb-0">
              {!isLast && (
                <span
                  className="absolute left-[11px] top-6 bottom-0 w-px bg-foreground/10"
                  aria-hidden
                />
              )}
              <Icon className={`mt-0.5 h-[22px] w-[22px] shrink-0 ${STATUS_CLASS[stage.status]}`} />
              <div className="min-w-0 flex-1 pt-0.5">
                <div className="flex flex-wrap items-baseline justify-between gap-2">
                  <p className="font-medium text-foreground">{stage.label}</p>
                  <span className="font-mono text-xs text-muted-foreground">
                    {stage.duration_ms > 0 ? `${stage.duration_ms.toFixed(1)} ms` : stage.status}
                  </span>
                </div>
                {stage.detail && (
                  <p className="mt-1 text-xs text-muted-foreground leading-relaxed">{stage.detail}</p>
                )}
              </div>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
