"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { LATENCY_TARGET_MS, RETRIEVAL_STAGES, STAGE_LABELS, type PipelineStageTrace } from "@/lib/types";

function stageMs(stage: PipelineStageTrace): number {
  return stage.duration_ms;
}

export function LatencyChart({ stages }: { stages: PipelineStageTrace[] }) {
  const data = stages
    .filter((stage) => stage.duration_ms > 0)
    .map((stage) => ({
      name: stage.label,
      ms: stageMs(stage),
    }));

  const retrievalMs = stages
    .filter((stage) =>
      ["guardrail", "embedding", "exact_cache", "semantic_cache", "retrieval", "rerank", "crag"].includes(
        stage.id,
      ),
    )
    .reduce((total, stage) => total + stage.duration_ms, 0);
  const withinTarget = retrievalMs < LATENCY_TARGET_MS;

  if (!data.length) {
    return <p className="text-sm text-muted-foreground">No stage timings recorded.</p>;
  }

  return (
    <div className="space-y-4">
      <div
        className={`rounded-lg border p-3 text-xs font-mono ${
          withinTarget
            ? "border-emerald-500/30 bg-emerald-500/5 text-emerald-800"
            : "border-amber-500/30 bg-amber-500/5 text-amber-900"
        }`}
      >
        Retrieval pipeline {retrievalMs.toFixed(1)} ms · target &lt; {LATENCY_TARGET_MS} ms
      </div>
      <div className="h-64 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 40 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.06)" />
            <XAxis
              dataKey="name"
              tick={{ fontSize: 10, fill: "rgba(0,0,0,0.5)" }}
              angle={-25}
              textAnchor="end"
              height={50}
            />
            <YAxis tick={{ fontSize: 10, fill: "rgba(0,0,0,0.5)" }} unit=" ms" />
            <Tooltip
              formatter={(value: number) => [`${value.toFixed(1)} ms`, "Duration"]}
              contentStyle={{ fontSize: 12 }}
            />
            <Bar dataKey="ms" fill="rgba(0,0,0,0.65)" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
      <p className="text-[11px] text-muted-foreground leading-relaxed">
        Bars reflect per-stage durations from the trace timeline. Console latency panels also track{" "}
        {RETRIEVAL_STAGES.map((key) => STAGE_LABELS[key]).join(", ")}.
      </p>
    </div>
  );
}
