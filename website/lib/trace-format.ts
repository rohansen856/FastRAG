import type { PipelineStageTrace, QueryResponse } from "@/lib/types";

/** Stages that make up the retrieval pipeline budget (everything before generation). */
export const RETRIEVAL_STAGE_IDS = new Set([
  "guardrail",
  "index_registry",
  "exact_cache",
  "embedding",
  "vector_guardrail",
  "semantic_cache",
  "retrieval",
  "rerank",
  "crag",
]);

export function formatMs(ms: number): string {
  if (ms >= 1000) return `${(ms / 1000).toFixed(ms >= 10_000 ? 1 : 2)} s`;
  if (ms >= 10) return `${Math.round(ms)} ms`;
  if (ms >= 1) return `${ms.toFixed(1)} ms`;
  if (ms > 0) return `${ms.toFixed(2)} ms`;
  return "0 ms";
}

export function retrievalMs(stages: PipelineStageTrace[]): number {
  return stages
    .filter((stage) => RETRIEVAL_STAGE_IDS.has(stage.id))
    .reduce((total, stage) => total + stage.duration_ms, 0);
}

export function shortHash(value: string | null | undefined, length = 12): string {
  if (!value) return "—";
  return value.length > length ? value.slice(0, length) : value;
}

/** The repository path a chunk title starts with ("src/x.py — Symbol" → "src/x.py"). */
export function sourcePath(title: string): { path: string; symbol: string | null } {
  const [path, ...rest] = title.split(" — ");
  return { path, symbol: rest.length ? rest.join(" — ") : null };
}

export type Verdict = {
  tone: "ok" | "warn" | "stop";
  label: string;
  sentence: string;
};

const GUARDRAIL_LABELS: Record<string, string> = {
  off_topic: "off-topic question",
  unsafe: "unsafe request",
  prompt_injection: "prompt injection",
  unsupported_language: "unsupported language",
  empty: "empty question",
};

export function guardrailLabel(rule: string | null | undefined): string {
  return (rule && GUARDRAIL_LABELS[rule]) ?? rule ?? "guardrail";
}

/** One sentence that says how the run ended and why. */
export function verdictFor(response: QueryResponse): Verdict {
  const total = formatMs(response.timings.total_ms);
  if (response.outcome === "refused") {
    const rule = guardrailLabel(response.guardrail?.rule);
    return {
      tone: "stop",
      label: "Refused",
      sentence: `Stopped before retrieval as a ${rule}${
        response.guardrail?.detail ? ` (${response.guardrail.detail})` : ""
      }, in ${total}.`,
    };
  }
  if (response.outcome === "no_answer") {
    return {
      tone: "warn",
      label: "Abstained",
      sentence: `The best sources were too weak to cite, so no answer was given. Took ${total}.`,
    };
  }
  const count = response.citations.length;
  const cached = response.cache_status !== "miss" ? `, served from the ${response.cache_status} cache` : "";
  return {
    tone: "ok",
    label: "Answered",
    sentence: `${count} source${count === 1 ? "" : "s"} cited${cached}, in ${total}.`,
  };
}
