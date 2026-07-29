"use client";

import type { CragTrace, GuardrailDecision, Transcript } from "@/lib/types";

const CRAG_COPY: Record<string, { label: string; detail: string; tone: string }> = {
  correct: {
    label: "Context accepted",
    detail: "Top reranker score cleared the confident band, so retrieval was used as-is.",
    tone: "border-emerald-500/40 bg-emerald-500/10 text-emerald-300",
  },
  ambiguous: {
    label: "Context refined",
    detail:
      "The score landed between the two bands, so passages were split into strips and only the relevant ones kept.",
    tone: "border-amber-500/40 bg-amber-500/10 text-amber-300",
  },
  incorrect: {
    label: "Query rewritten",
    detail:
      "Retrieval scored below the abstention gate, so the query was rewritten and retried once.",
    tone: "border-rose-500/40 bg-rose-500/10 text-rose-300",
  },
  disabled: {
    label: "CRAG disabled",
    detail: "Correction is turned off for this run.",
    tone: "border-slate-600 bg-slate-700/20 text-slate-300",
  },
};

const GUARDRAIL_LABELS: Record<string, string> = {
  off_topic: "Off topic",
  unsafe: "Unsafe request",
  prompt_injection: "Prompt injection",
  unsupported_language: "Unsupported language",
  empty: "Empty question",
};

interface Props {
  transcript: Transcript | null;
  guardrail: GuardrailDecision | null;
  crag: CragTrace | null;
}

export function DecisionTrace({ transcript, guardrail, crag }: Props) {
  if (!transcript && !guardrail && !crag) return null;
  const cragCopy = crag ? CRAG_COPY[crag.action] : null;

  return (
    <section className="rounded-xl border border-[var(--color-edge)] bg-[var(--color-panel)] p-5">
      <h2 className="mb-4 text-sm font-semibold tracking-wide text-slate-200 uppercase">
        Decision trace
      </h2>

      <div className="space-y-3">
        {transcript && (
          <Row title="Transcription" tone="border-sky-500/40 bg-sky-500/10 text-sky-300">
            <p className="text-slate-200">{transcript.text}</p>
            <p className="mt-1 text-xs text-[var(--color-muted)]">
              {transcript.provider} · {transcript.model}
              {transcript.language_code ? ` · ${transcript.language_code}` : ""} ·{" "}
              {transcript.duration_ms.toFixed(0)} ms
            </p>
          </Row>
        )}

        {guardrail && !guardrail.allowed && guardrail.rule && (
          <Row
            title={`Blocked: ${GUARDRAIL_LABELS[guardrail.rule] ?? guardrail.rule}`}
            tone="border-rose-500/40 bg-rose-500/10 text-rose-300"
          >
            <p className="text-xs text-[var(--color-muted)]">
              {guardrail.detail}
              {guardrail.score !== null && ` · similarity ${guardrail.score.toFixed(3)}`}
            </p>
          </Row>
        )}

        {crag && cragCopy && (
          <Row title={cragCopy.label} tone={cragCopy.tone}>
            <p className="text-xs text-[var(--color-muted)]">{cragCopy.detail}</p>
            <dl className="mt-2 flex flex-wrap gap-x-5 gap-y-1 text-xs">
              {crag.top_score !== null && (
                <Stat label="top score" value={crag.top_score.toFixed(3)} />
              )}
              {crag.kept_strips !== null && (
                <Stat label="strips kept" value={String(crag.kept_strips)} />
              )}
              {crag.rewrites > 0 && <Stat label="rewrites" value={String(crag.rewrites)} />}
            </dl>
            {crag.rewritten_query && (
              <p className="mt-2 rounded bg-slate-800/60 px-2 py-1 font-mono text-xs text-slate-300">
                → {crag.rewritten_query}
              </p>
            )}
          </Row>
        )}
      </div>
    </section>
  );
}

function Row({
  title,
  tone,
  children,
}: {
  title: string;
  tone: string;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-lg border border-[var(--color-edge)] p-3">
      <span className={`mb-2 inline-block rounded-full border px-2 py-0.5 text-xs ${tone}`}>
        {title}
      </span>
      {children}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex gap-1">
      <dt className="text-[var(--color-muted)]">{label}</dt>
      <dd className="font-mono text-slate-200">{value}</dd>
    </div>
  );
}
