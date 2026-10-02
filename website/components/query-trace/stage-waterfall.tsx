import type { PipelineStageTrace, QueryResponse } from "@/lib/types";
import { LATENCY_TARGET_MS } from "@/lib/types";
import { formatMs, retrievalMs } from "@/lib/trace-format";
import { TracePanel } from "./trace-panel";

/** Every stage the pipeline can record, in order; stages missing from a run were not reached. */
const PIPELINE: { id: string; label: string }[] = [
  { id: "stt", label: "Speech to text" },
  { id: "guardrail", label: "Text guardrails" },
  { id: "index_registry", label: "Index registry" },
  { id: "exact_cache", label: "Exact cache" },
  { id: "embedding", label: "Query embedding" },
  { id: "vector_guardrail", label: "Vector guardrail" },
  { id: "semantic_cache", label: "Semantic cache" },
  { id: "retrieval", label: "Hybrid retrieval" },
  { id: "rerank", label: "Cross-encoder rerank" },
  { id: "crag", label: "CRAG" },
  { id: "generation", label: "Answer generation" },
];

type Row = {
  id: string;
  label: string;
  stage: PipelineStageTrace | null;
  start: number;
};

/** Stages run one after another, so each starts where the previous one ended. */
function layout(stages: PipelineStageTrace[]): { rows: Row[]; recorded: number; notRun: number } {
  const byId = new Map(stages.map((stage) => [stage.id, stage]));
  let cursor = 0;
  const all = PIPELINE.filter((step) => step.id !== "stt" || byId.has("stt")).map((step) => {
    const stage = byId.get(step.id) ?? null;
    const row = { id: step.id, label: stage?.label ?? step.label, stage, start: cursor };
    cursor += stage?.duration_ms ?? 0;
    return row;
  });
  // Stages after the last one that ran are summarised in one line instead of listed.
  const last = all.findLastIndex((row) => row.stage !== null);
  const rows = all.slice(0, last + 1);
  return { rows, recorded: cursor, notRun: all.length - rows.length };
}

function tickLabel(ms: number): string {
  if (ms === 0) return "0";
  return ms >= 1000 ? `${Number((ms / 1000).toFixed(2))} s` : `${Number(ms.toFixed(2))} ms`;
}

function niceStep(max: number): number {
  const rough = max / 4;
  const power = 10 ** Math.floor(Math.log10(rough || 1));
  return [1, 2, 2.5, 5, 10].map((m) => m * power).find((step) => step >= rough) ?? power * 10;
}

const BAR_CLASS: Record<string, string> = {
  ok: "bg-foreground",
  skipped: "bg-foreground/25",
  blocked: "bg-rose-600",
};

export function StageWaterfall({ response }: { response: QueryResponse }) {
  const stages = response.trace?.stages ?? [];
  const { rows, recorded, notRun } = layout(stages);
  const total = Math.max(response.timings.total_ms, recorded);
  const outside = Math.max(0, response.timings.total_ms - recorded);
  const step = niceStep(total);
  const ticks = Array.from({ length: Math.floor(total / step) + 1 }, (_, i) => i * step);
  const pct = (ms: number) => `${(ms / total) * 100}%`;

  const retrieval = retrievalMs(stages);
  const local = response.trace?.profile === "local";
  const generation = response.trace?.generation;

  return (
    <TracePanel
      id="timing"
      title="Timing"
      aside={
        <span className="flex flex-wrap gap-x-5 gap-y-1">
          <span>
            total <span className="text-foreground">{formatMs(response.timings.total_ms)}</span>
          </span>
          <span>
            retrieval <span className="text-foreground">{formatMs(retrieval)}</span>
          </span>
          {response.timings.generation_ms > 0 && (
            <span>
              generation{" "}
              <span className="text-foreground">{formatMs(response.timings.generation_ms)}</span>
            </span>
          )}
          {generation?.total_tokens != null && (
            <span>
              tokens{" "}
              <span className="text-foreground">
                {generation.prompt_tokens} in · {generation.completion_tokens} out
              </span>
            </span>
          )}
        </span>
      }
    >
      <div className="grid grid-cols-[7rem_1fr_3.75rem] gap-x-3 text-sm sm:grid-cols-[13rem_1fr_5rem] sm:gap-x-4">
        {rows.map((row) => {
          const status = row.stage?.status ?? null;
          const reached = status !== null;
          const duration = row.stage?.duration_ms ?? 0;
          const detail = row.stage?.detail;
          return (
            <div key={row.id} className="contents group">
              <div className="min-w-0 border-b border-foreground/[0.06] py-2.5">
                <p className={`truncate ${reached ? "text-foreground" : "text-muted-foreground/60"}`}>
                  {row.label}
                </p>
                {detail && <p className="truncate text-xs text-muted-foreground">{detail}</p>}
              </div>
              <div className="relative border-b border-foreground/[0.06]">
                {ticks.map((tick) => (
                  <span
                    key={tick}
                    aria-hidden
                    className="absolute inset-y-0 w-px bg-foreground/[0.05]"
                    style={{ left: pct(tick) }}
                  />
                ))}
                {reached && (
                  <span
                    className={`absolute top-1/2 h-2.5 -translate-y-1/2 rounded-[2px] ${BAR_CLASS[status]}`}
                    style={{ left: pct(row.start), width: `max(2px, ${pct(duration)})` }}
                  />
                )}
              </div>
              <div
                className={`border-b border-foreground/[0.06] py-2.5 text-right tabular-nums ${
                  status === "blocked" ? "text-rose-700" : reached ? "text-foreground" : "text-muted-foreground/60"
                }`}
              >
                {status === "blocked"
                  ? "blocked"
                  : status === "skipped"
                    ? "skipped"
                    : reached
                      ? formatMs(duration)
                      : "not run"}
              </div>
            </div>
          );
        })}

        {outside > 1 && (
          <div className="contents">
            <div className="py-2.5">
              <p className="text-muted-foreground">Outside recorded stages</p>
              <p className="text-xs text-muted-foreground">network, cache writes, tracing</p>
            </div>
            <div className="relative">
              <span
                className="absolute top-1/2 h-2.5 -translate-y-1/2 rounded-[2px] border border-dashed border-foreground/30"
                style={{ left: pct(recorded), width: pct(outside) }}
              />
            </div>
            <div className="py-2.5 text-right text-muted-foreground tabular-nums">{formatMs(outside)}</div>
          </div>
        )}

        <div aria-hidden />
        <div aria-hidden className="relative h-6 text-[11px] text-muted-foreground tabular-nums">
          {ticks.map((tick, index) => (
            <span
              key={tick}
              className={`absolute top-1.5 -translate-x-1/2 whitespace-nowrap first:translate-x-0 ${index % 2 ? "max-sm:hidden" : ""}`}
              style={{ left: pct(tick) }}
            >
              {tickLabel(tick)}
            </span>
          ))}
        </div>
        <div aria-hidden />
      </div>

      <p className="mt-4 max-w-[68ch] text-sm leading-relaxed text-muted-foreground">
        {notRun > 0 && (
          <>
            The {notRun} later stage{notRun === 1 ? "" : "s"} did not run.{" "}
          </>
        )}
        {local ? (
          <>
            The retrieval pipeline took {formatMs(retrieval)} against the local profile&apos;s{" "}
            {LATENCY_TARGET_MS} ms budget
            {retrieval < LATENCY_TARGET_MS ? ", inside it." : ", over it."}
          </>
        ) : (
          <>
            This run used the {response.trace?.profile ?? "cloud"} profile, where every stage is a
            network call to a hosted service. The {LATENCY_TARGET_MS} ms retrieval budget applies to the
            local profile.
          </>
        )}{" "}
        Retrieval is every stage before generation.
      </p>
    </TracePanel>
  );
}
