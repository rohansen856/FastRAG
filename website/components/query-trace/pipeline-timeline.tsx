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

export function PipelineTimeline({ stages }: { stages: PipelineStageTrace[] }) {
  if (!stages.length) return null;

  return (
    <ol className="relative space-y-0">
      {stages.map((stage, index) => {
        const Icon = STATUS_ICON[stage.status];
        const isLast = index === stages.length - 1;
        return (
          <li key={`${stage.id}-${index}`} className="relative flex gap-4 pb-6 last:pb-0">
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
  );
}
