import type { QueryResponse } from "@/lib/types";
import { guardrailLabel } from "@/lib/trace-format";
import { TracePanel } from "./trace-panel";

const CRAG_OUTCOME: Record<string, string> = {
  correct: "cleared the confident band, so the context was used as retrieved.",
  ambiguous: "landed between the gate and the confident band, so passages were cut into strips and only relevant strips were kept.",
  incorrect: "fell below the gate, so CRAG rewrote the query and searched again.",
  disabled: "was not graded: CRAG was off for this run.",
};

/** The 0 to 1 rerank scale with this run's gate and confident band, and where its top score fell. */
function GateScale({
  score,
  gate,
  confident,
}: {
  score: number | null;
  gate: number;
  confident: number;
}) {
  const pct = (value: number) => `${Math.min(100, Math.max(0, value * 100))}%`;
  return (
    <figure className="mt-1">
      <div className="relative h-9">
        <div className="absolute inset-x-0 top-3 flex h-3 overflow-hidden rounded-[2px]">
          <span className="bg-foreground/[0.08]" style={{ width: pct(gate) }} />
          <span className="bg-foreground/[0.18]" style={{ width: pct(confident - gate) }} />
          <span className="flex-1 bg-foreground/[0.32]" />
        </div>
        {score !== null && (
          <span className="absolute top-0 flex -translate-x-1/2 flex-col items-center" style={{ left: pct(score) }}>
            <span className="h-[1.375rem] w-0.5 rounded-full bg-foreground" />
            <span className="mt-0.5 rounded-full bg-foreground px-1.5 text-[11px] leading-4 text-background tabular-nums">
              {score.toFixed(3)}
            </span>
          </span>
        )}
      </div>
      <figcaption className="mt-5 grid grid-cols-3 gap-2 text-[11px] leading-snug text-muted-foreground">
        <span>
          <span className="block text-foreground">Rewrite or abstain</span>below {gate.toFixed(3)}
        </span>
        <span>
          <span className="block text-foreground">Refine strips</span>
          {gate.toFixed(3)}–{confident.toFixed(3)}
        </span>
        <span className="text-right">
          <span className="block text-foreground">Accept</span>above {confident.toFixed(3)}
        </span>
      </figcaption>
    </figure>
  );
}

export function DecisionPanel({ response }: { response: QueryResponse }) {
  const { guardrail, crag, trace } = response;

  if (guardrail && !guardrail.allowed) {
    return (
      <TracePanel id="decision" title="Decision">
        <p className="text-sm leading-relaxed">
          <span className="font-medium text-rose-700">Blocked: {guardrailLabel(guardrail.rule)}.</span>{" "}
          <span className="text-muted-foreground">
            The text guardrail matched {guardrail.detail ? `an ${guardrail.detail}` : "this question"}
            {guardrail.score !== null ? ` (similarity ${guardrail.score.toFixed(3)})` : ""}. Guardrails run
            first, before anything is embedded or retrieved.
          </span>
        </p>
      </TracePanel>
    );
  }

  const gate = trace?.reranker_threshold ?? null;
  const confident = trace?.crag_confident_threshold ?? null;
  const top = crag?.top_score ?? trace?.reranked[0]?.score ?? null;

  return (
    <TracePanel id="decision" title="Decision" aside={crag ? `CRAG ${crag.action}` : undefined}>
      {gate !== null && confident !== null ? (
        <GateScale score={top} gate={gate} confident={confident} />
      ) : (
        <p className="text-sm text-muted-foreground">This run recorded no calibration thresholds.</p>
      )}

      <div className="mt-5 space-y-3 text-sm leading-relaxed">
        {crag && top !== null && (
          <p>
            <span className="text-muted-foreground">The top rerank score </span>
            <span className="tabular-nums">{top.toFixed(3)}</span>{" "}
            <span className="text-muted-foreground">{CRAG_OUTCOME[crag.action]}</span>
          </p>
        )}
        {crag?.rewritten_query && (
          <div>
            <p className="text-xs text-muted-foreground">Rewritten query</p>
            <p className="mt-1 border-l border-foreground/20 pl-3">{crag.rewritten_query}</p>
          </div>
        )}
        {trace?.abstention_reason && (
          <p className="text-muted-foreground">
            <span className="font-medium text-amber-800">Abstained.</span> {trace.abstention_reason}.
          </p>
        )}
        {crag?.kept_strips != null && (
          <p className="text-muted-foreground tabular-nums">{crag.kept_strips} strips kept.</p>
        )}
      </div>
    </TracePanel>
  );
}
