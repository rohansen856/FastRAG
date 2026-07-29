"use client";

import { useState } from "react";
import { runComparison } from "@/lib/api";
import { retrievalTotal } from "./LatencyPanel";
import type { QueryResponse } from "@/lib/types";

type Result = QueryResponse | { error: string };

const DESCRIPTIONS: Record<string, string> = {
  fixed: "Uniform word windows with overlap",
  sentence: "Sentence-packed to a budget",
  sentence_window: "One sentence indexed, window returned",
  semantic: "Split where meaning shifts",
  hierarchical: "Child retrieved, parent generated from",
  metadata_aware: "Provenance header prepended before embedding",
};

export function StrategyCompare({ strategies }: { strategies: string[] }) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<Record<string, Result> | null>(null);
  const [running, setRunning] = useState(false);

  const compare = async () => {
    if (!query.trim() || running) return;
    setRunning(true);
    setResults(null);
    try {
      // Every strategy lives in the same collection behind a payload filter, so
      // this is one query per strategy against identical data.
      setResults(await runComparison(query.trim(), strategies));
    } finally {
      setRunning(false);
    }
  };

  return (
    <section className="rounded-xl border border-[var(--color-edge)] bg-[var(--color-panel)] p-5">
      <h2 className="text-sm font-semibold tracking-wide text-slate-200 uppercase">
        Chunking comparison
      </h2>
      <p className="mt-1 mb-4 text-xs text-[var(--color-muted)]">
        Runs the same question against every indexed chunking strategy so retrieval quality and
        cost can be compared directly.
      </p>

      <div className="flex gap-2">
        <input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          onKeyDown={(event) => event.key === "Enter" && compare()}
          placeholder="Ask the same question of every strategy…"
          className="flex-1 rounded-lg border border-[var(--color-edge)] bg-[var(--color-surface)] px-3 py-2 text-sm outline-none focus:border-[var(--color-accent)]"
        />
        <button
          onClick={compare}
          disabled={running || !query.trim()}
          className="rounded-lg bg-[var(--color-accent-soft)] px-4 py-2 text-sm font-medium text-slate-950 disabled:opacity-40"
        >
          {running ? "Running…" : "Compare"}
        </button>
      </div>

      {results && (
        <div className="mt-4 overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="text-xs tracking-wide text-[var(--color-muted)] uppercase">
              <tr className="border-b border-[var(--color-edge)]">
                <th className="py-2 pr-4 font-medium">Strategy</th>
                <th className="py-2 pr-4 font-medium">Outcome</th>
                <th className="py-2 pr-4 font-medium">Sources</th>
                <th className="py-2 pr-4 font-medium">Retrieval</th>
                <th className="py-2 font-medium">Total</th>
              </tr>
            </thead>
            <tbody>
              {strategies.map((strategy) => (
                <Row key={strategy} strategy={strategy} result={results[strategy]} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

function Row({ strategy, result }: { strategy: string; result: Result | undefined }) {
  const failed = !result || "error" in result;
  return (
    <tr className="border-b border-[var(--color-edge)]/60 align-top">
      <td className="py-3 pr-4">
        <div className="text-slate-200">{strategy}</div>
        <div className="text-xs text-[var(--color-muted)]">{DESCRIPTIONS[strategy]}</div>
      </td>
      {failed ? (
        <td colSpan={4} className="py-3 text-xs text-rose-300">
          {result && "error" in result ? result.error.slice(0, 160) : "not indexed"}
        </td>
      ) : (
        <>
          <td className="py-3 pr-4 text-slate-300">{result.outcome}</td>
          <td className="py-3 pr-4 font-mono text-slate-300">{result.citations.length}</td>
          <td className="py-3 pr-4 font-mono text-slate-300">
            {retrievalTotal(result.timings).toFixed(0)} ms
          </td>
          <td className="py-3 font-mono text-slate-300">{result.timings.total_ms.toFixed(0)} ms</td>
        </>
      )}
    </tr>
  );
}
