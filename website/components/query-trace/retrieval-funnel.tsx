"use client";

import { useState } from "react";
import type { ChunkTrace } from "@/lib/types";

type Tab = "retrieved" | "reranked" | "contexts";

const TAB_LABELS: Record<Tab, string> = {
  retrieved: "Retrieved",
  reranked: "Reranked",
  contexts: "Context to LLM",
};

function ScoreBar({ score, max }: { score: number; max: number }) {
  const width = max > 0 ? Math.max(4, (score / max) * 100) : 0;
  return (
    <div className="h-1.5 w-full overflow-hidden rounded-full bg-foreground/10">
      <div className="h-full rounded-full bg-foreground/60" style={{ width: `${width}%` }} />
    </div>
  );
}

function ChunkTable({
  rows,
  citedIds,
}: {
  rows: ChunkTrace[];
  citedIds: Set<string>;
}) {
  const maxScore = Math.max(...rows.map((row) => row.score), 0.001);

  if (!rows.length) {
    return <p className="text-sm text-muted-foreground">No chunks at this stage.</p>;
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[520px] text-sm">
        <thead>
          <tr className="border-b border-foreground/10 text-left text-xs font-mono uppercase tracking-widest text-muted-foreground">
            <th className="py-2 pr-3">#</th>
            <th className="py-2 pr-3">Title</th>
            <th className="py-2 pr-3 w-28">Score</th>
            <th className="py-2">Excerpt</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr
              key={row.chunk_id}
              className={`border-b border-foreground/5 align-top ${
                citedIds.has(row.chunk_id) ? "bg-emerald-500/5" : ""
              }`}
            >
              <td className="py-3 pr-3 font-mono text-xs text-muted-foreground">{row.rank}</td>
              <td className="py-3 pr-3">
                <p className="font-medium">{row.title}</p>
                <p className="font-mono text-[10px] text-muted-foreground break-all">{row.chunk_id}</p>
                {row.refined && (
                  <span className="mt-1 inline-block rounded border border-foreground/15 px-1.5 py-0.5 text-[10px] font-mono">
                    refined
                  </span>
                )}
              </td>
              <td className="py-3 pr-3">
                <span className="font-mono text-xs">{row.score.toFixed(3)}</span>
                <div className="mt-1">
                  <ScoreBar score={row.score} max={maxScore} />
                </div>
              </td>
              <td className="py-3 text-muted-foreground leading-relaxed">{row.excerpt}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function RetrievalFunnel({
  retrieved,
  reranked,
  contexts,
  citedChunkIds,
}: {
  retrieved: ChunkTrace[];
  reranked: ChunkTrace[];
  contexts: ChunkTrace[];
  citedChunkIds: string[];
}) {
  const [tab, setTab] = useState<Tab>("retrieved");
  const cited = new Set(citedChunkIds);
  const rows = tab === "retrieved" ? retrieved : tab === "reranked" ? reranked : contexts;

  return (
    <div>
      <div className="mb-4 flex flex-wrap gap-2">
        {(Object.keys(TAB_LABELS) as Tab[]).map((key) => (
          <button
            key={key}
            type="button"
            onClick={() => setTab(key)}
            className={`rounded-full border px-3 py-1 text-xs font-mono transition-colors ${
              tab === key
                ? "border-foreground bg-foreground text-background"
                : "border-foreground/15 text-muted-foreground hover:text-foreground"
            }`}
          >
            {TAB_LABELS[key]} (
            {key === "retrieved"
              ? retrieved.length
              : key === "reranked"
                ? reranked.length
                : contexts.length}
            )
          </button>
        ))}
      </div>
      <ChunkTable rows={rows} citedIds={cited} />
    </div>
  );
}
