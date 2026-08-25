import type { CragTrace, GuardrailDecision, Transcript } from "@/lib/types";

const CRAG_COPY: Record<string, { label: string; detail: string }> = {
  correct: {
    label: "Context accepted",
    detail: "Top reranker score cleared the confident band.",
  },
  ambiguous: {
    label: "Context refined",
    detail: "Passages were split into strips; only relevant strips kept.",
  },
  incorrect: {
    label: "Query rewritten",
    detail: "Retrieval scored below the abstention gate; query rewritten once.",
  },
  disabled: {
    label: "CRAG disabled",
    detail: "Correction is turned off for this run.",
  },
};

const GUARDRAIL_LABELS: Record<string, string> = {
  off_topic: "Off topic",
  unsafe: "Unsafe request",
  prompt_injection: "Prompt injection",
  unsupported_language: "Unsupported language",
  empty: "Empty question",
};

export function DecisionPanel({
  guardrail,
  crag,
  abstentionReason,
}: {
  guardrail: GuardrailDecision | null;
  crag: CragTrace | null;
  abstentionReason: string | null;
}) {
  const cragCopy = crag ? CRAG_COPY[crag.action] : null;

  return (
    <div className="space-y-4">
      {guardrail && !guardrail.allowed && guardrail.rule && (
        <div className="rounded-lg border border-rose-500/25 bg-rose-500/5 p-4">
          <p className="text-sm font-medium text-rose-800">
            Blocked: {GUARDRAIL_LABELS[guardrail.rule] ?? guardrail.rule}
          </p>
          <p className="mt-1 text-xs text-muted-foreground leading-relaxed">
            {guardrail.detail}
            {guardrail.score !== null && ` · similarity ${guardrail.score.toFixed(3)}`}
          </p>
        </div>
      )}

      {crag && cragCopy && (
        <div className="rounded-lg border border-foreground/10 bg-foreground/[0.02] p-4">
          <p className="text-sm font-medium">{cragCopy.label}</p>
          <p className="mt-1 text-xs text-muted-foreground">{cragCopy.detail}</p>
          <dl className="mt-3 flex flex-wrap gap-x-5 gap-y-1 text-xs font-mono">
            {crag.top_score !== null && (
              <div>
                <dt className="text-muted-foreground">top score</dt>
                <dd>{crag.top_score.toFixed(3)}</dd>
              </div>
            )}
            {crag.kept_strips !== null && (
              <div>
                <dt className="text-muted-foreground">strips kept</dt>
                <dd>{crag.kept_strips}</dd>
              </div>
            )}
            {crag.rewrites > 0 && (
              <div>
                <dt className="text-muted-foreground">rewrites</dt>
                <dd>{crag.rewrites}</dd>
              </div>
            )}
          </dl>
          {crag.rewritten_query && (
            <p className="mt-2 rounded bg-foreground/[0.04] px-2 py-1 font-mono text-xs">
              → {crag.rewritten_query}
            </p>
          )}
        </div>
      )}

      {abstentionReason && (
        <div className="rounded-lg border border-foreground/10 bg-foreground/[0.02] p-4">
          <p className="text-sm font-medium">Abstention</p>
          <p className="mt-1 text-xs text-muted-foreground leading-relaxed">{abstentionReason}</p>
        </div>
      )}

      {!guardrail && !crag && !abstentionReason && (
        <p className="text-sm text-muted-foreground">No guardrail or CRAG decisions recorded.</p>
      )}
    </div>
  );
}

export function TranscriptPanel({ transcript }: { transcript: Transcript | null }) {
  if (!transcript) return null;
  return (
    <div className="rounded-lg border border-sky-500/20 bg-sky-500/5 p-4">
      <p className="text-sm text-foreground leading-relaxed">{transcript.text}</p>
      <p className="mt-2 text-xs font-mono text-muted-foreground">
        {transcript.provider} · {transcript.model}
        {transcript.language_code ? ` · ${transcript.language_code}` : ""} ·{" "}
        {transcript.duration_ms.toFixed(0)} ms
      </p>
    </div>
  );
}
