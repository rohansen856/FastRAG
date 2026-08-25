"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { Navigation } from "@/components/landing/navigation";
import { FooterSection } from "@/components/landing/footer-section";
import { CitationsPanel } from "@/components/query-trace/citations-panel";
import { DecisionPanel, TranscriptPanel } from "@/components/query-trace/decision-panel";
import { LatencyChart } from "@/components/query-trace/latency-chart";
import { ModelsPanel } from "@/components/query-trace/models-panel";
import { PipelineDiagram } from "@/components/query-trace/pipeline-diagram";
import { PipelineTimeline } from "@/components/query-trace/pipeline-timeline";
import { RankingChart } from "@/components/query-trace/ranking-chart";
import { RetrievalFunnel } from "@/components/query-trace/retrieval-funnel";
import { TraceHeader } from "@/components/query-trace/trace-header";
import { TraceSection } from "@/components/query-trace/trace-section";
import { loadQueryTrace, type StoredQueryTrace } from "@/lib/query-trace-store";

export default function QueryTracePage() {
  const params = useParams<{ queryId: string }>();
  const queryId = params.queryId;
  const [stored, setStored] = useState<StoredQueryTrace | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    setStored(loadQueryTrace(queryId));
    setReady(true);
  }, [queryId]);

  const trace = stored?.response.trace;

  return (
    <main className="relative min-h-screen overflow-x-hidden noise-overlay">
      <Navigation />
      <div className="pt-28 lg:pt-32 pb-16">
        <div className="max-w-[1100px] mx-auto px-6 lg:px-12">
          {!ready ? null : !stored || !trace ? (
            <div className="max-w-lg space-y-4">
              <h1 className="text-3xl font-display tracking-tight">Trace not found</h1>
              <p className="text-muted-foreground leading-relaxed">
                Pipeline traces are stored in this browser session only. Run a question on the home
                page first, then open the trace from the conversation section.
              </p>
              <Link
                href="/"
                className="inline-flex rounded-full border border-foreground/20 px-4 py-2 text-sm font-mono hover:bg-foreground hover:text-background transition-colors"
              >
                Go to home
              </Link>
            </div>
          ) : (
            <>
              <TraceHeader stored={stored} response={stored.response} />
              <div className="grid gap-6 lg:grid-cols-2">
                <TraceSection delay={0}>
                  <h2 className="mb-4 text-xs font-mono uppercase tracking-widest text-muted-foreground">
                    Timeline
                  </h2>
                  <PipelineTimeline stages={trace.stages} />
                </TraceSection>
                <TraceSection delay={80}>
                  <h2 className="mb-4 text-xs font-mono uppercase tracking-widest text-muted-foreground">
                    Flow
                  </h2>
                  <PipelineDiagram
                    stages={trace.stages}
                    cacheStatus={stored.response.cache_status}
                    outcome={stored.response.outcome}
                  />
                </TraceSection>
              </div>

              <div className="mt-6 grid gap-6 lg:grid-cols-2">
                <TraceSection delay={120}>
                  <h2 className="mb-4 text-xs font-mono uppercase tracking-widest text-muted-foreground">
                    Latency
                  </h2>
                  <LatencyChart stages={trace.stages} />
                </TraceSection>
                <TraceSection delay={160}>
                  <h2 className="mb-4 text-xs font-mono uppercase tracking-widest text-muted-foreground">
                    Models & index
                  </h2>
                  <ModelsPanel trace={trace} />
                </TraceSection>
              </div>

              <div className="mt-6 grid gap-6 lg:grid-cols-2">
                <TraceSection delay={200}>
                  <h2 className="mb-4 text-xs font-mono uppercase tracking-widest text-muted-foreground">
                    Decisions
                  </h2>
                  <DecisionPanel
                    guardrail={stored.response.guardrail}
                    crag={stored.response.crag}
                    abstentionReason={trace.abstention_reason}
                  />
                </TraceSection>
                {stored.response.transcript && (
                  <TraceSection delay={240}>
                    <h2 className="mb-4 text-xs font-mono uppercase tracking-widest text-muted-foreground">
                      Transcript
                    </h2>
                    <TranscriptPanel transcript={stored.response.transcript} />
                  </TraceSection>
                )}
              </div>

              <TraceSection className="mt-6" delay={280}>
                <h2 className="mb-4 text-xs font-mono uppercase tracking-widest text-muted-foreground">
                  Retrieval funnel
                </h2>
                <RetrievalFunnel
                  retrieved={trace.retrieved}
                  reranked={trace.reranked}
                  contexts={trace.contexts}
                  citedChunkIds={trace.cited_chunk_ids}
                />
              </TraceSection>

              <div className="mt-6 grid gap-6 lg:grid-cols-2">
                <TraceSection delay={320}>
                  <h2 className="mb-4 text-xs font-mono uppercase tracking-widest text-muted-foreground">
                    Rerank scores
                  </h2>
                  <RankingChart ranked={trace.reranked} />
                </TraceSection>
                <TraceSection delay={360}>
                  <h2 className="mb-4 text-xs font-mono uppercase tracking-widest text-muted-foreground">
                    Citations
                  </h2>
                  <CitationsPanel citations={stored.response.citations} />
                </TraceSection>
              </div>
            </>
          )}
        </div>
      </div>
      <FooterSection />
    </main>
  );
}
