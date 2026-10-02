"use client";

import { useState } from "react";
import { ChevronDown } from "lucide-react";
import type { ChunkTrace, QueryResponse } from "@/lib/types";
import { sourcePath } from "@/lib/trace-format";
import { TracePanel } from "./trace-panel";

type Step = "retrieved" | "reranked" | "contexts" | "cited";

const STEP_COPY: Record<Step, { label: string; note: string }> = {
  retrieved: {
    label: "Retrieved",
    note: "Hybrid search candidates, scored by reciprocal rank fusion of the dense and sparse legs.",
  },
  reranked: {
    label: "Reranked",
    note: "Cross-encoder relevance from 0 to 1. The markers are this run's abstention gate and CRAG confident band.",
  },
  contexts: {
    label: "Sent to model",
    note: "The top reranked chunks that went into the prompt.",
  },
  cited: {
    label: "Cited",
    note: "Chunks the answer's citation markers point to, after validation.",
  },
};

const COLLAPSED_ROWS = 8;

function ScoreBar({
  score,
  scale,
  marks,
}: {
  score: number;
  scale: number;
  marks: { at: number; label: string }[];
}) {
  return (
    <span className="relative block h-1.5 w-full rounded-full bg-foreground/[0.07]">
      <span
        className="absolute inset-y-0 left-0 rounded-full bg-foreground/70"
        style={{ width: `${Math.max(2, Math.min(100, (score / scale) * 100))}%` }}
      />
      {marks.map((mark) => (
        <span
          key={mark.label}
          title={`${mark.label} ${mark.at.toFixed(3)}`}
          className="absolute -inset-y-1 w-px bg-foreground"
          style={{ left: `${(mark.at / scale) * 100}%` }}
        />
      ))}
    </span>
  );
}

function ChunkRow({
  chunk,
  scale,
  marks,
  citation,
}: {
  chunk: ChunkTrace;
  scale: number;
  marks: { at: number; label: string }[];
  citation: number | null;
}) {
  const [open, setOpen] = useState(false);
  const { path, symbol } = sourcePath(chunk.title);
  return (
    <li className="border-b border-foreground/[0.06]">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
        className="grid w-full grid-cols-[2rem_1fr_auto] items-center gap-x-3 py-3 text-left transition-colors hover:bg-foreground/[0.02] focus-visible:bg-foreground/[0.03] focus-visible:outline-none sm:grid-cols-[2rem_1fr_10rem_3.5rem_1rem]"
      >
        <span className="text-xs text-muted-foreground tabular-nums">{chunk.rank}</span>
        <span className="min-w-0">
          <span className="flex items-baseline gap-2">
            <span className="truncate">{path}</span>
            {citation !== null && (
              <span className="shrink-0 rounded-full border border-emerald-600/40 px-1.5 text-[11px] text-emerald-800 tabular-nums">
                cited {citation}
              </span>
            )}
            {chunk.refined && (
              <span className="shrink-0 rounded-full border border-foreground/20 px-1.5 text-[11px] text-muted-foreground">
                refined
              </span>
            )}
          </span>
          {symbol && <span className="block truncate text-xs text-muted-foreground">{symbol}</span>}
        </span>
        <span className="hidden sm:block">
          <ScoreBar score={chunk.score} scale={scale} marks={marks} />
        </span>
        <span className="text-right text-sm tabular-nums">{chunk.score.toFixed(3)}</span>
        <ChevronDown
          className={`hidden h-4 w-4 text-muted-foreground transition-transform duration-200 sm:block ${open ? "rotate-180" : ""}`}
        />
      </button>
      {open && (
        <div className="pb-4 pl-[2.75rem] pr-2">
          <p className="whitespace-pre-wrap break-words font-mono text-[13px] leading-relaxed text-muted-foreground">
            {chunk.excerpt}
          </p>
          <p className="mt-2 text-[11px] text-muted-foreground/80 tabular-nums">chunk {chunk.chunk_id}</p>
        </div>
      )}
    </li>
  );
}

export function EvidencePanel({ response }: { response: QueryResponse }) {
  const trace = response.trace;
  const citedNumber = new Map(response.citations.map((citation) => [citation.chunk_id, citation.number]));
  const seen = new Set<string>();
  const cited = [...(trace?.contexts ?? []), ...(trace?.reranked ?? [])].filter((chunk) => {
    if (!citedNumber.has(chunk.chunk_id) || seen.has(chunk.chunk_id)) return false;
    seen.add(chunk.chunk_id);
    return true;
  });
  const lists: Record<Step, ChunkTrace[]> = {
    retrieved: trace?.retrieved ?? [],
    reranked: trace?.reranked ?? [],
    contexts: trace?.contexts ?? [],
    cited,
  };
  const [step, setStep] = useState<Step>(lists.reranked.length ? "reranked" : "retrieved");
  const [expanded, setExpanded] = useState(false);

  const rows = lists[step];
  const visible = expanded ? rows : rows.slice(0, COLLAPSED_ROWS);
  const fused = step === "retrieved";
  const scale = fused ? Math.max(...rows.map((row) => row.score), 0.001) : 1;
  const marks =
    step === "reranked" && trace
      ? [
          ...(trace.reranker_threshold != null ? [{ at: trace.reranker_threshold, label: "gate" }] : []),
          ...(trace.crag_confident_threshold != null
            ? [{ at: trace.crag_confident_threshold, label: "confident" }]
            : []),
        ]
      : [];

  if (!lists.retrieved.length && !lists.reranked.length) {
    return (
      <TracePanel id="evidence" title="Evidence">
        <p className="max-w-[68ch] text-sm leading-relaxed text-muted-foreground">
          Nothing was retrieved. The run ended before the retrieval stage, so there are no chunks to
          inspect.
        </p>
      </TracePanel>
    );
  }

  return (
    <TracePanel id="evidence" title="Evidence">
      <div role="tablist" aria-label="Retrieval funnel" className="flex flex-wrap items-stretch border-b border-foreground/10">
        {(Object.keys(STEP_COPY) as Step[]).map((key) => {
          const selected = key === step;
          return (
            <button
              key={key}
              type="button"
              role="tab"
              aria-selected={selected}
              onClick={() => {
                setStep(key);
                setExpanded(false);
              }}
              className={`-mb-px flex items-baseline gap-2 border-b-2 px-3 py-2.5 text-sm transition-colors first:pl-0 ${
                selected
                  ? "border-foreground text-foreground"
                  : "border-transparent text-muted-foreground hover:text-foreground"
              }`}
            >
              {STEP_COPY[key].label}
              <span className="tabular-nums text-xs text-muted-foreground">{lists[key].length}</span>
            </button>
          );
        })}
      </div>

      <p className="mt-3 max-w-[68ch] text-xs leading-relaxed text-muted-foreground">
        {STEP_COPY[step].note}
      </p>

      {rows.length ? (
        <ol className="mt-3 border-t border-foreground/10">
          {visible.map((chunk) => (
            <ChunkRow
              key={`${step}-${chunk.chunk_id}`}
              chunk={chunk}
              scale={scale}
              marks={marks}
              citation={citedNumber.get(chunk.chunk_id) ?? null}
            />
          ))}
        </ol>
      ) : (
        <p className="mt-4 text-sm text-muted-foreground">
          {step === "cited" || step === "contexts"
            ? "No chunk reached this step: the run abstained before generation."
            : "No chunks at this step."}
        </p>
      )}

      {rows.length > COLLAPSED_ROWS && (
        <button
          type="button"
          onClick={() => setExpanded((value) => !value)}
          className="mt-3 text-sm text-muted-foreground underline decoration-foreground/25 underline-offset-4 hover:text-foreground"
        >
          {expanded ? "Show fewer" : `Show all ${rows.length}`}
        </button>
      )}
    </TracePanel>
  );
}
