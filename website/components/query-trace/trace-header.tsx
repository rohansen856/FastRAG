import Link from "next/link";
import type { QueryResponse } from "@/lib/types";
import type { StoredQueryTrace } from "@/lib/query-trace-store";

const OUTCOME_LABELS: Record<string, string> = {
  answered: "Answered",
  no_answer: "Abstained",
  refused: "Refused",
};

export function TraceHeader({
  stored,
  response,
}: {
  stored: StoredQueryTrace;
  response: QueryResponse;
}) {
  return (
    <header className="mb-10 space-y-6">
      <Link
        href="/#answer"
        className="inline-flex items-center gap-2 text-sm font-mono text-muted-foreground hover:text-foreground transition-colors"
      >
        ← Back to conversation
      </Link>
      <div>
        <span className="inline-flex items-center gap-3 text-sm font-mono text-muted-foreground mb-4">
          <span className="w-8 h-px bg-foreground/30" />
          pipeline trace
        </span>
        <h1 className="text-3xl lg:text-4xl font-display tracking-tight mb-3">Query pipeline</h1>
        <p className="text-lg text-foreground leading-relaxed max-w-3xl">{stored.question}</p>
      </div>
      <div className="flex flex-wrap items-center gap-2 text-xs font-mono">
        <span className="rounded-full border border-foreground/15 px-2.5 py-0.5">
          {OUTCOME_LABELS[response.outcome] ?? response.outcome}
        </span>
        {response.cache_status !== "miss" && (
          <span className="rounded-full border border-foreground/15 px-2.5 py-0.5 text-muted-foreground">
            {response.cache_status} cache
          </span>
        )}
        {stored.scopeMode && (
          <span className="rounded-full border border-foreground/15 px-2.5 py-0.5 text-muted-foreground">
            {stored.scopeMode === "document" ? "Attached files" : "Full corpus"}
          </span>
        )}
        <span className="rounded-full border border-foreground/15 px-2.5 py-0.5 text-muted-foreground">
          query {response.query_id.slice(0, 8)}…
        </span>
        <span className="rounded-full border border-foreground/15 px-2.5 py-0.5 text-muted-foreground">
          trace {response.trace_id.slice(0, 8)}…
        </span>
      </div>
    </header>
  );
}
