import type { QueryOverrides, QueryTrace } from "./types";

export interface PipelineConfigForm {
  strategy: string;
  language: string;
  skipCache: boolean;
  cragEnabled: boolean;
  candidateK: string;
  contextTopK: string;
  rerankerThreshold: string;
  cragConfidentThreshold: string;
  offtopicThreshold: string;
  llmModel: string;
  llmBaseUrl: string;
  llmApiKey: string;
  llmMaxTokens: string;
}

export const LANGUAGES = [
  { code: "", label: "Auto detect" },
  { code: "hi-IN", label: "Hindi" },
  { code: "bn-IN", label: "Bengali" },
  { code: "ta-IN", label: "Tamil" },
  { code: "te-IN", label: "Telugu" },
  { code: "mr-IN", label: "Marathi" },
  { code: "en-IN", label: "English (IN)" },
];

function thresholdEqual(a: number | null | undefined, b: number): boolean {
  if (a == null) return false;
  return Math.abs(a - b) < 0.001;
}

export function configFromTrace(trace: QueryTrace, defaultStrategy: string): PipelineConfigForm {
  const cragStage = trace.stages.find((stage) => stage.id === "crag");
  const cragEnabled = cragStage ? cragStage.status !== "skipped" : true;
  return {
    strategy: trace.strategy || defaultStrategy,
    language: trace.language ?? "",
    skipCache: false,
    cragEnabled,
    candidateK: String(trace.candidate_k || 20),
    contextTopK: String(trace.context_top_k || 5),
    rerankerThreshold: trace.reranker_threshold?.toFixed(3) ?? "0.500",
    cragConfidentThreshold: trace.crag_confident_threshold?.toFixed(3) ?? "0.700",
    offtopicThreshold: trace.offtopic_threshold?.toFixed(3) ?? "0.300",
    llmModel: trace.generator_model ?? "",
    llmBaseUrl: "",
    llmApiKey: "",
    llmMaxTokens: "",
  };
}

export function buildOverrides(form: PipelineConfigForm, trace: QueryTrace): QueryOverrides {
  const overrides: QueryOverrides = {};
  if (form.skipCache) overrides.skip_cache = true;

  const baselineCrag = trace.stages.find((stage) => stage.id === "crag");
  const baselineCragEnabled = baselineCrag ? baselineCrag.status !== "skipped" : true;
  if (form.cragEnabled !== baselineCragEnabled) overrides.crag_enabled = form.cragEnabled;

  const candidateK = Number(form.candidateK);
  if (Number.isFinite(candidateK) && candidateK !== trace.candidate_k) {
    overrides.candidate_k = candidateK;
  }

  const contextTopK = Number(form.contextTopK);
  if (Number.isFinite(contextTopK) && contextTopK !== trace.context_top_k) {
    overrides.context_top_k = contextTopK;
  }

  const rerankerThreshold = Number(form.rerankerThreshold);
  if (
    Number.isFinite(rerankerThreshold) &&
    !thresholdEqual(trace.reranker_threshold, rerankerThreshold)
  ) {
    overrides.reranker_threshold = rerankerThreshold;
  }

  const cragConfident = Number(form.cragConfidentThreshold);
  if (
    Number.isFinite(cragConfident) &&
    !thresholdEqual(trace.crag_confident_threshold, cragConfident)
  ) {
    overrides.crag_confident_threshold = cragConfident;
  }

  const offtopic = Number(form.offtopicThreshold);
  if (Number.isFinite(offtopic) && !thresholdEqual(trace.offtopic_threshold, offtopic)) {
    overrides.offtopic_threshold = offtopic;
  }

  const llm: QueryOverrides["llm"] = {};
  if (form.llmModel.trim() && form.llmModel.trim() !== (trace.generator_model ?? "")) {
    llm.model = form.llmModel.trim();
  }
  if (form.llmBaseUrl.trim()) llm.base_url = form.llmBaseUrl.trim();
  if (form.llmApiKey.trim()) llm.api_key = form.llmApiKey.trim();
  const maxTokens = Number(form.llmMaxTokens);
  if (Number.isFinite(maxTokens) && maxTokens > 0) llm.max_tokens = maxTokens;
  if (Object.keys(llm).length) overrides.llm = llm;

  return overrides;
}

export function friendlyQueryError(raw: string): string {
  const text = raw.trim();
  let detail = text;
  try {
    const parsed = JSON.parse(text) as { detail?: unknown; error?: unknown };
    if (typeof parsed.detail === "string") detail = parsed.detail;
    else if (typeof parsed.error === "string") detail = parsed.error;
  } catch {
    // plain string
  }
  const lower = `${detail} ${text}`.toLowerCase();
  if (
    lower.includes("cannot reach") ||
    lower.includes("fetch failed") ||
    lower.includes("econnrefused") ||
    lower.includes("networkerror")
  ) {
    return "Can't reach the API right now. Start the FastRAG server and try again.";
  }
  if (lower.includes("overrides are disabled")) {
    return "Query overrides are disabled on this deployment. Set FASTRAG_ALLOW_QUERY_OVERRIDES=true.";
  }
  if (lower.includes("deadline exceeded") || lower.includes("503")) {
    return "That took too long upstream. Try again.";
  }
  return detail.length > 240 ? `${detail.slice(0, 237)}…` : detail;
}
