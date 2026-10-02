import type { StoredQueryTrace } from "@/lib/query-trace-store";
import { verdictFor } from "@/lib/trace-format";
import { OutcomeDot } from "./outcome-dot";

const TONE_TEXT = {
  ok: "text-emerald-800",
  warn: "text-amber-800",
  stop: "text-rose-700",
} as const;

function recordedLabel(savedAt: number): string {
  return new Date(savedAt).toLocaleString(undefined, {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function TraceHeader({
  run,
  example,
  compare,
}: {
  run: StoredQueryTrace;
  example: boolean;
  compare?: {
    mode: "baseline" | "active";
    onChange: (mode: "baseline" | "active") => void;
  };
}) {
  const { response } = run;
  const verdict = verdictFor(response);
  const overrides = response.trace?.overrides_applied;
  const overridden = Boolean(overrides && Object.keys(overrides).length);

  return (
    <header className="pb-10 pt-10 lg:pt-14">
      <h1 className="max-w-[28ch] text-balance font-display text-3xl leading-[1.1] tracking-tight lg:text-5xl">
        {run.question}
      </h1>

      <p className="mt-5 flex max-w-[68ch] items-baseline gap-2.5 text-lg leading-relaxed">
        <OutcomeDot outcome={response.outcome} className="-translate-y-0.5" />
        <span>
          <span className={`font-medium ${TONE_TEXT[verdict.tone]}`}>{verdict.label}.</span>{" "}
          <span className="text-muted-foreground">{verdict.sentence}</span>
        </span>
      </p>

      <div className="mt-6 flex flex-wrap items-center gap-x-4 gap-y-3 text-sm text-muted-foreground">
        {compare && (
          <div className="inline-flex rounded-full border border-foreground/15 p-0.5" role="group" aria-label="Which run to show">
            {(["baseline", "active"] as const).map((mode) => (
              <button
                key={mode}
                type="button"
                aria-pressed={compare.mode === mode}
                onClick={() => compare.onChange(mode)}
                className={`rounded-full px-3 py-1 transition-colors ${
                  compare.mode === mode ? "bg-foreground text-background" : "hover:text-foreground"
                }`}
              >
                {mode === "baseline" ? "Original" : "Re-run"}
              </button>
            ))}
          </div>
        )}
        <span>
          {example ? "Recorded example" : "This session"} · {recordedLabel(run.savedAt)}
        </span>
        {response.trace && (
          <span>
            {response.trace.profile} profile · {response.trace.strategy} chunks
          </span>
        )}
        {run.scopeMode === "document" && <span>attached files only</span>}
        {overridden && <span className="text-amber-800">overrides applied</span>}
      </div>
    </header>
  );
}
