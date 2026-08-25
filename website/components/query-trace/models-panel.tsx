import type { QueryTrace } from "@/lib/types";

function Row({ label, value }: { label: string; value: string | null | undefined }) {
  if (!value) return null;
  return (
    <div className="flex flex-wrap items-baseline justify-between gap-2 py-2 border-b border-foreground/5 last:border-0">
      <dt className="text-xs font-mono uppercase tracking-widest text-muted-foreground">{label}</dt>
      <dd className="text-sm font-mono text-foreground text-right break-all">{value}</dd>
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
      <Row label="STT" value={trace.stt_provider ? `${trace.stt_provider} · ${trace.stt_model}` : undefined} />
      <Row label="Candidate K" value={String(trace.candidate_k)} />
      <Row label="Context top K" value={String(trace.context_top_k)} />
      <Row label="Rerank threshold" value={trace.reranker_threshold?.toFixed(3)} />
      <Row label="CRAG confident" value={trace.crag_confident_threshold?.toFixed(3)} />
      <Row label="Off-topic threshold" value={trace.offtopic_threshold?.toFixed(3)} />
    </dl>
  );
}
