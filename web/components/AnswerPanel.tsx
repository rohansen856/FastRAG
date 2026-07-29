"use client";

import type { Citation, QueryResponse } from "@/lib/types";

const OUTCOME_STYLES: Record<string, string> = {
  answered: "border-emerald-500/40 bg-emerald-500/10 text-emerald-300",
  no_answer: "border-slate-500/40 bg-slate-500/10 text-slate-300",
  refused: "border-rose-500/40 bg-rose-500/10 text-rose-300",
};

const OUTCOME_LABELS: Record<string, string> = {
  answered: "Answered",
  no_answer: "Abstained",
  refused: "Refused",
};

interface Props {
  answer: string;
  streaming: boolean;
  response: QueryResponse | null;
}

export function AnswerPanel({ answer, streaming, response }: Props) {
  const citations = response?.citations ?? [];
  const outcome = response?.outcome;

  return (
    <section className="rounded-xl border border-[var(--color-edge)] bg-[var(--color-panel)] p-5">
      <header className="mb-3 flex flex-wrap items-center gap-2">
        <h2 className="text-sm font-semibold tracking-wide text-slate-200 uppercase">Answer</h2>
        {outcome && (
          <span className={`rounded-full border px-2 py-0.5 text-xs ${OUTCOME_STYLES[outcome]}`}>
            {OUTCOME_LABELS[outcome]}
          </span>
        )}
        {response?.cache_status && response.cache_status !== "miss" && (
          <span className="rounded-full border border-sky-500/40 bg-sky-500/10 px-2 py-0.5 text-xs text-sky-300">
            {response.cache_status} cache hit
          </span>
        )}
        {response?.generator_provider && (
          <span className="rounded-full border border-slate-600 px-2 py-0.5 text-xs text-[var(--color-muted)]">
            {response.generator_provider}
          </span>
        )}
      </header>

      {answer ? (
        <p className="leading-relaxed whitespace-pre-wrap text-slate-100">
          {answer}
          {streaming && <span className="ml-0.5 animate-pulse text-[var(--color-accent)]">▍</span>}
        </p>
      ) : (
        <p className="text-sm text-[var(--color-muted)]">
          {streaming ? "Waiting for the first validated sentence…" : "Ask a question to begin."}
        </p>
      )}

      {citations.length > 0 && <CitationList citations={citations} />}
    </section>
  );
}

function CitationList({ citations }: { citations: Citation[] }) {
  return (
    <div className="mt-5 border-t border-[var(--color-edge)] pt-4">
      <h3 className="mb-2 text-xs font-semibold tracking-wide text-[var(--color-muted)] uppercase">
        Sources
      </h3>
      <ol className="space-y-2">
        {citations.map((citation) => (
          <li key={citation.chunk_id} className="flex gap-3 text-sm">
            <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded bg-[var(--color-accent-soft)]/20 font-mono text-xs text-[var(--color-accent)]">
              {citation.number}
            </span>
            <div className="min-w-0">
              <p className="truncate text-slate-200">{citation.title}</p>
              <p className="mt-0.5 line-clamp-2 text-xs text-[var(--color-muted)]">
                {citation.excerpt}
              </p>
            </div>
          </li>
        ))}
      </ol>
    </div>
  );
}
