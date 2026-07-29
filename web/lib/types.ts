export type Outcome = "answered" | "no_answer" | "refused";
export type CacheStatus = "miss" | "exact" | "semantic";
export type CragAction = "correct" | "ambiguous" | "incorrect" | "disabled";
export type GuardrailRule =
  | "off_topic"
  | "unsafe"
  | "prompt_injection"
  | "unsupported_language"
  | "empty";

export interface Citation {
  number: number;
  document_id: string;
  chunk_id: string;
  title: string;
  source_uri: string;
  page: number | null;
  excerpt: string;
}

export interface QueryTimings {
  total_ms: number;
  stt_ms: number;
  guardrail_ms: number;
  embedding_ms: number;
  cache_ms: number;
  retrieval_ms: number;
  rerank_ms: number;
  crag_ms: number;
  generation_ms: number;
}

export interface GuardrailDecision {
  allowed: boolean;
  rule: GuardrailRule | null;
  detail: string | null;
  score: number | null;
}

export interface CragTrace {
  action: CragAction;
  top_score: number | null;
  rewrites: number;
  rewritten_query: string | null;
  kept_strips: number | null;
}

export interface Transcript {
  text: string;
  language_code: string | null;
  provider: string;
  model: string;
  duration_ms: number;
}

export interface QueryResponse {
  query_id: string;
  trace_id: string;
  outcome: Outcome;
  answer: string;
  citations: Citation[];
  cache_status: CacheStatus;
  index_version: string;
  timings: QueryTimings;
  guardrail: GuardrailDecision | null;
  crag: CragTrace | null;
  transcript: Transcript | null;
  generator_provider: string | null;
}

export interface Percentiles {
  p50: number;
  p70: number;
  p95: number;
  p100: number;
  mean: number;
  count: number;
}

export interface BenchReport {
  label: string;
  samples: number;
  failures: number;
  retrieval_pipeline_ms: Percentiles;
  meets_200ms_p50: boolean;
  meets_200ms_p95: boolean;
  ttft_ms: Percentiles;
  stages: Record<string, Percentiles>;
  outcomes: Record<string, number>;
  cache: Record<string, number>;
  crag: Record<string, number>;
}

/** Stages that make up the sub-200ms retrieval budget, in pipeline order. */
export const RETRIEVAL_STAGES = [
  "guardrail_ms",
  "embedding_ms",
  "cache_ms",
  "retrieval_ms",
  "rerank_ms",
  "crag_ms",
] as const;

export const STAGE_LABELS: Record<string, string> = {
  stt_ms: "Speech to text",
  guardrail_ms: "Guardrails",
  embedding_ms: "Embedding",
  cache_ms: "Cache",
  retrieval_ms: "Hybrid retrieval",
  rerank_ms: "Reranking",
  crag_ms: "CRAG",
  generation_ms: "Generation",
  total_ms: "Total",
};

export const LATENCY_TARGET_MS = 200;
