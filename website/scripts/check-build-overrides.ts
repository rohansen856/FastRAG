/** Verify buildOverrides produces the payload we expect from custom form edits. */
import { buildOverrides, configFromTrace } from "../lib/query-config";
import type { QueryTrace } from "../lib/types";

const baseline: QueryTrace = {
  query_id: "q1",
  trace_id: "t1",
  strategy: "sentence",
  language: null,
  document_ids: [],
  candidate_k: 20,
  context_top_k: 5,
  reranker_threshold: 0.6893056,
  crag_confident_threshold: 0.796,
  offtopic_threshold: -0.12087279678330676,
  generator_model: "openai/gpt-oss-20b",
  embedder_model: "jina",
  reranker_model: "jina",
  index_version: "v1",
  stages: [
    { id: "crag", name: "CRAG", status: "ok", duration_ms: 1 },
  ],
  retrieved: [],
  reranked: [],
  contexts: [],
  cited_chunk_ids: [],
  abstention_reason: null,
};

const unchanged = configFromTrace(baseline, "sentence");
const noop = buildOverrides(unchanged, baseline);
if (Object.keys(noop).length !== 0) {
  console.error("FAIL: unchanged form should produce no overrides", noop);
  process.exit(1);
}

const custom = {
  ...unchanged,
  skipCache: true,
  cragEnabled: false,
  candidateK: "12",
  contextTopK: "2",
  rerankerThreshold: "0.250",
  cragConfidentThreshold: "0.550",
  offtopicThreshold: "-0.450",
  llmModel: "openai/gpt-oss-20b",
  llmBaseUrl: "https://api.openai.com/v1",
  llmApiKey: "test-key",
  llmMaxTokens: "180",
};

const overrides = buildOverrides(custom, baseline);
const expected = {
  skip_cache: true,
  crag_enabled: false,
  candidate_k: 12,
  context_top_k: 2,
  reranker_threshold: 0.25,
  crag_confident_threshold: 0.55,
  offtopic_threshold: -0.45,
  llm: {
    base_url: "https://api.openai.com/v1",
    api_key: "test-key",
    max_tokens: 180,
  },
};

for (const [key, value] of Object.entries(expected)) {
  const actual = (overrides as Record<string, unknown>)[key];
  if (JSON.stringify(actual) !== JSON.stringify(value)) {
    console.error(`FAIL: overrides.${key}`, actual, "!=", value);
    process.exit(1);
  }
}
if (overrides.llm?.model) {
  console.error("FAIL: llm.model should not be sent when unchanged", overrides.llm.model);
  process.exit(1);
}

console.log("buildOverrides checks passed");
