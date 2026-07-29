"use client";

import {
  LATENCY_TARGET_MS,
  RETRIEVAL_STAGES,
  STAGE_LABELS,
  type QueryTimings,
} from "@/lib/types";

const BAR_COLORS: Record<string, string> = {
  stt_ms: "bg-fuchsia-400",
  guardrail_ms: "bg-emerald-400",
  embedding_ms: "bg-sky-400",
  cache_ms: "bg-cyan-300",
  retrieval_ms: "bg-indigo-400",
  rerank_ms: "bg-violet-400",
  crag_ms: "bg-amber-400",
  generation_ms: "bg-rose-400",
};

export function retrievalTotal(timings: QueryTimings): number {
  return RETRIEVAL_STAGES.reduce((total, stage) => total + (timings[stage] ?? 0), 0);
}

export function LatencyPanel({ timings }: { timings: QueryTimings }) {
  const retrieval = retrievalTotal(timings);
  const withinTarget = retrieval < LATENCY_TARGET_MS;
  const stages = Object.keys(STAGE_LABELS).filter(
    (stage) => stage !== "total_ms" && (timings[stage as keyof QueryTimings] ?? 0) > 0,
  );
  const largest = Math.max(...stages.map((s) => timings[s as keyof QueryTimings] ?? 0), 1);

  return (
    <section className="rounded-xl border border-[var(--color-edge)] bg-[var(--color-panel)] p-5">
      <header className="mb-4 flex items-baseline justify-between gap-4">
        <h2 className="text-sm font-semibold tracking-wide text-slate-200 uppercase">Latency</h2>
        <span className="text-xs text-[var(--color-muted)]">
          total {timings.total_ms.toFixed(0)} ms
        </span>
      </header>

      <div
        className={`mb-4 rounded-lg border p-3 ${
          withinTarget
            ? "border-emerald-500/40 bg-emerald-500/10"
            : "border-amber-500/40 bg-amber-500/10"
        }`}
      >
        <div className="flex items-baseline justify-between">
          <span className="text-xs text-[var(--color-muted)]">
            Retrieval pipeline (target &lt; {LATENCY_TARGET_MS} ms)
          </span>
          <span
            className={`font-mono text-lg ${withinTarget ? "text-emerald-300" : "text-amber-300"}`}
          >
            {retrieval.toFixed(1)} ms
          </span>
        </div>
        <p className="mt-1 text-[11px] leading-relaxed text-[var(--color-muted)]">
          Guardrails, embedding, cache, retrieval, reranking and CRAG. Speech-to-text and token
          generation are shown separately because both are bound by the upstream provider.
        </p>
      </div>

      <ul className="space-y-2">
        {stages.map((stage) => {
          const value = timings[stage as keyof QueryTimings] ?? 0;
          return (
            <li key={stage} className="grid grid-cols-[130px_1fr_64px] items-center gap-3">
              <span className="text-xs text-[var(--color-muted)]">{STAGE_LABELS[stage]}</span>
              <div className="h-2 overflow-hidden rounded-full bg-slate-800">
                <div
                  className={`h-full rounded-full ${BAR_COLORS[stage] ?? "bg-slate-500"}`}
                  style={{ width: `${Math.max(2, (value / largest) * 100)}%` }}
                />
              </div>
              <span className="text-right font-mono text-xs text-slate-300">
                {value.toFixed(1)}
              </span>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
