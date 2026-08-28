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
  compareMode = "active",
  hasBaseline = false,
  onCompareModeChange,
  isRerunView = false,
}: {
  stored: StoredQueryTrace;
  response: QueryResponse;
  compareMode?: "active" | "baseline";
  hasBaseline?: boolean;
  onCompareModeChange?: (mode: "active" | "baseline") => void;
  isRerunView?: boolean;
}) {
  const overrides = response.trace?.overrides_applied;

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

      {hasBaseline && onCompareModeChange && (
        <div className="inline-flex rounded-full border border-foreground/15 p-1 text-xs font-mono">
          <button
            type="button"
            onClick={() => onCompareModeChange("baseline")}
            className={`rounded-full px-3 py-1 transition-colors ${
              compareMode === "baseline"
                ? "bg-foreground text-background"
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            Original run
          </button>
          <button
            type="button"
            onClick={() => onCompareModeChange("active")}
            className={`rounded-full px-3 py-1 transition-colors ${
              compareMode === "active"
                ? "bg-foreground text-background"
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            Latest re-run
          </button>
        </div>
      )}

      <div className="flex flex-wrap items-center gap-2 text-xs font-mono">
        <span className="rounded-full border border-foreground/15 px-2.5 py-0.5">
          {OUTCOME_LABELS[response.outcome] ?? response.outcome}
        </span>
        {isRerunView && (
          <span className="rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2.5 py-0.5 text-emerald-900">
            Re-run
          </span>
        )}
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
        {overrides && Object.keys(overrides).length > 0 && (
          <span className="rounded-full border border-amber-500/30 bg-amber-500/10 px-2.5 py-0.5 text-amber-900">
            Overrides applied
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
