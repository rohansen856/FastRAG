"use client";

import { Info } from "lucide-react";
import type { QueryTrace } from "@/lib/types";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

const FIELD_HELP: Record<string, string> = {
  Profile: "Runtime profile: local (ONNX + Compose) or cloud (hosted providers).",
  Strategy: "Chunking strategy used for retrieval - sentence, window, or hierarchical.",
  Collection: "Qdrant collection name holding the vector index for this query.",
  "Index version": "Content-version hash of the indexed corpus; changes when documents are re-ingested.",
  "Cache namespace": "Hash isolating this cache bucket - ties answers to model, prompt, and index version.",
  Embedder: "Fingerprint of the embedding model that encoded the query vector.",
  Reranker: "Fingerprint of the cross-encoder used to rescore retrieved chunks.",
  Generator: "LLM model ID used to stream the grounded answer.",
  Provider: "Upstream inference provider that served generation (e.g. Groq, OpenAI).",
  STT: "Speech-to-text provider and model when the query came from voice input.",
  "Candidate K": "Maximum chunks retrieved from hybrid search before reranking.",
  "Context top K": "Maximum reranked chunks considered for the LLM context window.",
  "Rerank threshold": "Calibrated minimum rerank score; below this the pipeline abstains.",
  "CRAG confident": "Score band above which CRAG trusts retrieval without refinement.",
  "Off-topic threshold": "Minimum cosine similarity to the corpus centroid; lower scores are refused.",
};

function Row({
  label,
  value,
}: {
  label: string;
  value: string | null | undefined;
}) {
  if (!value) return null;
  const help = FIELD_HELP[label];

  return (
    <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-1 py-2 border-b border-foreground/5 last:border-0">
      <dt className="flex items-center gap-1.5 text-xs font-mono uppercase tracking-widest text-muted-foreground">
        {label}
        {help && (
          <Tooltip>
            <TooltipTrigger asChild>
              <button
                type="button"
                className="inline-flex rounded-full text-muted-foreground/70 hover:text-foreground transition-colors"
                aria-label={`About ${label}`}
              >
                <Info className="h-3 w-3" />
              </button>
            </TooltipTrigger>
            <TooltipContent side="top" className="max-w-[240px] text-left leading-relaxed">
              {help}
            </TooltipContent>
          </Tooltip>
        )}
      </dt>
      <dd className="text-sm font-mono text-foreground text-right break-all max-w-[65%]">{value}</dd>
    </div>
  );
}

export function ModelsPanel({ trace }: { trace: QueryTrace }) {
  return (
    <dl>
      <Row label="Profile" value={trace.profile} />
      <Row label="Strategy" value={trace.strategy} />
      <Row label="Collection" value={trace.collection_name} />
      <Row label="Index version" value={trace.content_version} />
      <Row label="Cache namespace" value={trace.cache_namespace} />
      <Row label="Embedder" value={trace.embedding_fingerprint} />
      <Row label="Reranker" value={trace.reranker_fingerprint} />
      <Row label="Generator" value={trace.generator_model} />
      <Row label="Provider" value={trace.generator_provider ?? undefined} />
      <Row
        label="STT"
        value={trace.stt_provider ? `${trace.stt_provider} · ${trace.stt_model}` : undefined}
      />
      <Row label="Candidate K" value={String(trace.candidate_k)} />
      <Row label="Context top K" value={String(trace.context_top_k)} />
      <Row label="Rerank threshold" value={trace.reranker_threshold?.toFixed(3)} />
      <Row label="CRAG confident" value={trace.crag_confident_threshold?.toFixed(3)} />
      <Row label="Off-topic threshold" value={trace.offtopic_threshold?.toFixed(3)} />
    </dl>
  );
}
