"use client";

import { useEffect, useRef } from "react";
import type { Citation, QueryResponse } from "@/lib/types";

const OUTCOME_LABELS: Record<string, string> = {
  answered: "Answered",
  no_answer: "Abstained",
  refused: "Refused",
};

const OUTCOME_CLASS: Record<string, string> = {
  answered: "border-foreground/20 bg-foreground/[0.03] text-foreground",
  no_answer: "border-foreground/15 bg-foreground/[0.02] text-muted-foreground",
  refused: "border-rose-500/30 bg-rose-500/5 text-rose-700",
};

interface Props {
  question: string;
  answer: string;
  streaming: boolean;
  response: QueryResponse | null;
  error: string | null;
  attachedCount?: number;
  scopeMode?: "document" | "corpus" | null;
}

export function AnswerChatSection({
  question,
  answer,
  streaming,
  response,
  error,
  attachedCount = 0,
  scopeMode,
}: Props) {
  const sectionRef = useRef<HTMLElement>(null);
  const visible = Boolean(streaming || answer || response || error);

  useEffect(() => {
    if (!visible || !sectionRef.current) return;
    sectionRef.current.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [visible, question]);

  if (!visible) return null;

  const citations = response?.citations ?? [];
  const outcome = response?.outcome;
  const displayAnswer = answer || response?.answer || "";

  return (
    <section
      id="answer"
      ref={sectionRef}
      className="relative border-y border-foreground/10 bg-foreground/[0.015] scroll-mt-28"
    >
      <div className="max-w-[900px] mx-auto px-6 lg:px-12 py-16 lg:py-20">
        <div className="flex items-center gap-3 mb-8">
          <span className="w-8 h-px bg-foreground/30" />
          <span className="text-sm font-mono text-muted-foreground">Conversation</span>
        </div>

        <div className="space-y-6">
          {question && (
            <div className="flex justify-end">
              <div className="max-w-[85%] rounded-2xl rounded-br-md bg-foreground text-background px-5 py-3 text-base leading-relaxed">
                {question}
              </div>
            </div>
          )}

          <div className="flex justify-start">
            <div className="w-full max-w-[95%] rounded-2xl rounded-bl-md border border-foreground/10 bg-background px-5 py-5 shadow-sm">
              <div className="mb-4 flex flex-wrap items-center gap-2">
                {outcome && (
                  <span
                    className={`rounded-full border px-2.5 py-0.5 text-xs font-mono ${OUTCOME_CLASS[outcome] ?? OUTCOME_CLASS.answered}`}
                  >
                    {OUTCOME_LABELS[outcome] ?? outcome}
                  </span>
                )}
                {response?.cache_status && response.cache_status !== "miss" && (
                  <span className="rounded-full border border-foreground/15 px-2.5 py-0.5 text-xs font-mono text-muted-foreground">
                    {response.cache_status} cache
                  </span>
                )}
                {response?.crag?.action && response.crag.action !== "disabled" && (
                  <span className="rounded-full border border-foreground/15 px-2.5 py-0.5 text-xs font-mono text-muted-foreground">
                    CRAG · {response.crag.action}
                  </span>
                )}
                {attachedCount > 0 && scopeMode && (
                  <span className="rounded-full border border-foreground/15 px-2.5 py-0.5 text-xs font-mono text-muted-foreground">
                    {scopeMode === "document"
                      ? attachedCount === 1
                        ? "Attached document"
                        : `${attachedCount} attached documents`
                      : "Full corpus"}
                  </span>
                )}
                {streaming && !displayAnswer && (
                  <span className="text-xs font-mono text-muted-foreground">Streaming…</span>
                )}
              </div>

              {error ? (
                <p className="text-rose-700 text-sm leading-relaxed">{error}</p>
              ) : displayAnswer ? (
                <div className="text-[1.05rem] leading-[1.7] text-foreground">
                  <FormattedAnswer text={displayAnswer} citations={citations} streaming={streaming} />
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">
                  Waiting for the first grounded sentence…
                </p>
              )}

              {citations.length > 0 && (
                <div className="mt-8 pt-6 border-t border-foreground/10">
                  <h3 className="mb-4 text-xs font-mono tracking-widest uppercase text-muted-foreground">
                    Sources
                  </h3>
                  <ol className="space-y-4">
                    {citations.map((citation) => (
                      <li
                        key={citation.chunk_id}
                        id={`source-${citation.number}`}
                        className="scroll-mt-32 flex gap-3 text-sm"
                      >
                        <a
                          href={`#cite-${citation.number}`}
                          className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full border border-foreground/20 font-mono text-xs text-foreground hover:bg-foreground hover:text-background transition-colors"
                        >
                          {citation.number}
                        </a>
                        <div className="min-w-0 space-y-1">
                          <p className="font-medium text-foreground">{citation.title}</p>
                          <p className="text-muted-foreground leading-relaxed">{citation.excerpt}</p>
                          <CitationLink uri={citation.source_uri} />
                        </div>
                      </li>
                    ))}
                  </ol>
                </div>
              )}

              {response?.timings && !streaming && (
                <p className="mt-6 text-xs font-mono text-muted-foreground">
                  {response.timings.total_ms.toFixed(0)} ms total
                  {response.generator_provider ? ` · ${response.generator_provider}` : ""}
                </p>
              )}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

function FormattedAnswer({
  text,
  citations,
  streaming,
}: {
  text: string;
  citations: Citation[];
  streaming: boolean;
}) {
  const parts = text.split(/(\[\d+\])/g);
  return (
    <p className="whitespace-pre-wrap">
      {parts.map((part, index) => {
        const match = part.match(/^\[(\d+)\]$/);
        if (match) {
          const n = match[1];
          const exists = citations.some((c) => String(c.number) === n);
          if (!exists) {
            return (
              <sup key={`${part}-${index}`} className="text-muted-foreground ml-0.5">
                {part}
              </sup>
            );
          }
          return (
            <a
              key={`${part}-${index}`}
              id={`cite-${n}`}
              href={`#source-${n}`}
              className="ml-0.5 inline-flex translate-y-[-0.15em] items-center justify-center rounded px-1 font-mono text-[0.7em] text-foreground/70 underline decoration-foreground/30 underline-offset-2 hover:bg-foreground hover:text-background hover:no-underline"
            >
              [{n}]
            </a>
          );
        }
        return <span key={`${index}-${part.slice(0, 8)}`}>{part}</span>;
      })}
      {streaming && <span className="ml-0.5 inline-block h-4 w-0.5 animate-pulse bg-foreground align-middle" />}
    </p>
  );
}

function CitationLink({ uri }: { uri: string }) {
  if (!uri) return null;
  const isHttp = /^https?:\/\//i.test(uri);
  if (isHttp) {
    return (
      <a
        href={uri}
        target="_blank"
        rel="noopener noreferrer"
        className="inline-block font-mono text-xs text-foreground/60 hover:text-foreground underline underline-offset-4"
      >
        {uri}
      </a>
    );
  }
  return <span className="inline-block font-mono text-xs text-muted-foreground break-all">{uri}</span>;
}
