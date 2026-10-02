import { ArrowUpRight, Ban, CircleHelp } from "lucide-react";
import type { Citation, QueryResponse } from "@/lib/types";
import { guardrailLabel, sourcePath } from "@/lib/trace-format";
import { TracePanel } from "./trace-panel";

/** Renders `[n]` markers as links to the source list and `**bold**` as strong text. */
function AnswerText({ text, citations }: { text: string; citations: Citation[] }) {
  const known = new Set(citations.map((citation) => String(citation.number)));
  return (
    <p className="max-w-[68ch] text-lg leading-relaxed text-foreground">
      {text.split(/(\[\d+\]|\*\*[^*]+\*\*)/g).map((part, index) => {
        const marker = part.match(/^\[(\d+)\]$/);
        if (marker) {
          return known.has(marker[1]) ? (
            <a
              key={index}
              href={`#source-${marker[1]}`}
              className="mx-0.5 inline-flex h-5 min-w-5 -translate-y-px items-center justify-center rounded-full border border-foreground/20 px-1 align-middle text-[11px] tabular-nums text-foreground/80 transition-colors hover:border-foreground hover:bg-foreground hover:text-background"
            >
              {marker[1]}
            </a>
          ) : (
            <sup key={index} className="text-muted-foreground">
              {part}
            </sup>
          );
        }
        if (part.startsWith("**") && part.endsWith("**")) {
          return (
            <strong key={index} className="font-medium">
              {part.slice(2, -2)}
            </strong>
          );
        }
        return <span key={index}>{part}</span>;
      })}
    </p>
  );
}

function Sources({ citations }: { citations: Citation[] }) {
  return (
    <ol className="mt-8 divide-y divide-foreground/10 border-y border-foreground/10">
      {citations.map((citation) => {
        const { path, symbol } = sourcePath(citation.title);
        const href = /^https?:\/\//i.test(citation.source_uri) ? citation.source_uri : null;
        const lines = href?.match(/#L(\d+)-L(\d+)$/);
        return (
          <li
            key={citation.chunk_id}
            id={`source-${citation.number}`}
            className="grid scroll-mt-28 grid-cols-[1.75rem_1fr] gap-x-3 py-4 target:bg-foreground/[0.03]"
          >
            <span className="flex h-6 w-6 items-center justify-center rounded-full border border-foreground/20 text-xs tabular-nums">
              {citation.number}
            </span>
            <div className="min-w-0">
              <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
                {href ? (
                  <a
                    href={href}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="group inline-flex items-center gap-1 font-medium underline decoration-foreground/25 underline-offset-4 hover:decoration-foreground"
                  >
                    {path}
                    <ArrowUpRight className="h-3.5 w-3.5 text-muted-foreground group-hover:text-foreground" />
                  </a>
                ) : (
                  <span className="font-medium">{path}</span>
                )}
                {symbol && <span className="text-sm text-muted-foreground">{symbol}</span>}
                {lines && (
                  <span className="text-xs text-muted-foreground tabular-nums">
                    lines {lines[1]}–{lines[2]}
                  </span>
                )}
              </div>
              <p className="mt-2 line-clamp-2 font-mono text-[13px] leading-relaxed text-muted-foreground">
                {citation.excerpt}
              </p>
            </div>
          </li>
        );
      })}
    </ol>
  );
}

function Withheld({
  icon,
  title,
  children,
}: {
  icon: React.ReactNode;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex max-w-[68ch] gap-4">
      <span className="mt-1 text-muted-foreground">{icon}</span>
      <div>
        <p className="text-lg leading-relaxed">{title}</p>
        <div className="mt-2 text-sm leading-relaxed text-muted-foreground">{children}</div>
      </div>
    </div>
  );
}

export function AnswerPanel({
  response,
  streamingText,
}: {
  response: QueryResponse;
  streamingText?: string;
}) {

  return (
    <TracePanel
      id="answer"
      title="Answer"
      aside={
        response.citations.length
          ? `${response.citations.length} source${response.citations.length === 1 ? "" : "s"} cited`
          : undefined
      }
    >
      {response.outcome === "refused" ? (
        <Withheld icon={<Ban className="h-5 w-5" />} title="No answer was generated.">
          The text guardrail classified the question as a {guardrailLabel(response.guardrail?.rule)}
          {response.guardrail?.detail ? ` (${response.guardrail.detail})` : ""}, so nothing was
          embedded, retrieved or sent to the model.
        </Withheld>
      ) : response.outcome === "no_answer" ? (
        <Withheld icon={<CircleHelp className="h-5 w-5" />} title={`“${response.answer}”`}>
          FastRAG answers only from sources it can cite, and none of the retrieved chunks scored
          high enough. Decision shows the top score against the gate.
        </Withheld>
      ) : (
        <>
          <AnswerText text={streamingText || response.answer} citations={response.citations} />
          {response.citations.length > 0 && <Sources citations={response.citations} />}
        </>
      )}
    </TracePanel>
  );
}
