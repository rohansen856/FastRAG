"use client";

import { useEffect, useState } from "react";
import { LATENCY_TARGET_MS, STAGE_LABELS, type BenchReport } from "@/lib/types";

type Summary = Record<string, BenchReport | string>;

export function BenchDashboard() {
  const [summary, setSummary] = useState<Summary | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch("/api/rag/v1/bench")
      .then(async (response) => {
        if (!response.ok) throw new Error("no benchmark report published yet");
        setSummary(await response.json());
      })
      .catch((cause) => setError(String(cause.message ?? cause)));
  }, []);

  const reports = Object.entries(summary ?? {}).filter(
    (entry): entry is [string, BenchReport] => typeof entry[1] === "object",
  );

  return (
    <section className="rounded-xl border border-[var(--color-edge)] bg-[var(--color-panel)] p-5">
      <h2 className="text-sm font-semibold tracking-wide text-slate-200 uppercase">
        Benchmark dashboard
      </h2>
      <p className="mt-1 mb-4 text-xs text-[var(--color-muted)]">
        Published by <code className="text-slate-300">scripts/bench-latency.py</code>. The local
        profile runs in-process models and is where the sub-200ms target is measured; the cloud
        profile runs entirely on free hosted tiers.
      </p>

      {error && <p className="text-xs text-[var(--color-muted)]">{error}</p>}

      <div className="grid gap-4 md:grid-cols-2">
        {reports.map(([label, report]) => (
          <ReportCard key={label} label={label} report={report} />
        ))}
      </div>
    </section>
  );
}

function ReportCard({ label, report }: { label: string; report: BenchReport }) {
  const retrieval = report.retrieval_pipeline_ms;
  return (
    <article className="rounded-lg border border-[var(--color-edge)] p-4">
      <header className="mb-3 flex items-center justify-between">
        <h3 className="font-medium text-slate-200 capitalize">{label} profile</h3>
        <span
          className={`rounded-full border px-2 py-0.5 text-xs ${
            report.meets_200ms_p95
              ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-300"
              : "border-amber-500/40 bg-amber-500/10 text-amber-300"
          }`}
        >
          {report.meets_200ms_p95 ? `< ${LATENCY_TARGET_MS} ms at P95` : "over target at P95"}
        </span>
      </header>

      <p className="mb-3 text-xs text-[var(--color-muted)]">
        {report.samples} samples · {report.failures} failures
      </p>

      <div className="mb-4 grid grid-cols-4 gap-2 text-center">
        {(["p50", "p70", "p95", "p100"] as const).map((key) => (
          <div key={key} className="rounded bg-slate-800/60 p-2">
            <div className="text-[10px] tracking-wide text-[var(--color-muted)] uppercase">
              {key}
            </div>
            <div className="font-mono text-sm text-slate-100">{retrieval?.[key]?.toFixed(0)}</div>
          </div>
        ))}
      </div>

      <table className="w-full text-left text-xs">
        <thead className="text-[var(--color-muted)]">
          <tr>
            <th className="pb-1 font-medium">Stage</th>
            <th className="pb-1 text-right font-medium">P50</th>
            <th className="pb-1 text-right font-medium">P70</th>
            <th className="pb-1 text-right font-medium">P100</th>
          </tr>
        </thead>
        <tbody>
          {Object.entries(report.stages)
            .filter(([, value]) => value && value.p100 > 0)
            .map(([stage, value]) => (
              <tr key={stage} className="border-t border-[var(--color-edge)]/50">
                <td className="py-1 text-slate-300">{STAGE_LABELS[stage] ?? stage}</td>
                <td className="py-1 text-right font-mono text-slate-400">{value.p50.toFixed(0)}</td>
                <td className="py-1 text-right font-mono text-slate-400">{value.p70.toFixed(0)}</td>
                <td className="py-1 text-right font-mono text-slate-400">
                  {value.p100.toFixed(0)}
                </td>
              </tr>
            ))}
        </tbody>
      </table>
    </article>
  );
}
