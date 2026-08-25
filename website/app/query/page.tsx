"use client";

import Link from "next/link";
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
import { TraceSection, TraceSectionTitle } from "@/components/query-trace/trace-section";
import { loadLatestQueryTrace, type StoredQueryTrace } from "@/lib/query-trace-store";

export default function QueryTracePage() {
  const [stored, setStored] = useState<StoredQueryTrace | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    setStored(loadLatestQueryTrace());
    setReady(true);
  }, []);

  const trace = stored?.response.trace;
  const hasTranscript = Boolean(stored?.response.transcript);

  return (
    <main className="relative min-h-screen overflow-x-hidden noise-overlay">
      <Navigation />
      <div className="pt-28 lg:pt-32 pb-16">
        <div className="mx-auto w-full max-w-[1440px] px-4 sm:px-6 lg:px-10">
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

              <div className="grid grid-cols-1 gap-4 lg:grid-cols-3 lg:gap-5 lg:auto-rows-min">
                {/* Row 1: path overview (compact) then timeline detail */}
                <TraceSection className="lg:col-span-3" delay={0}>
                  <TraceSectionTitle>Path taken</TraceSectionTitle>
                  <PipelineDiagram
                    stages={trace.stages}
                    cacheStatus={stored.response.cache_status}
                    outcome={stored.response.outcome}
                  />
                </TraceSection>

                <TraceSection className="lg:col-span-2" delay={60}>
                  <TraceSectionTitle>Timeline</TraceSectionTitle>
                  <PipelineTimeline
                    stages={trace.stages}
                    generationMs={stored.response.timings.generation_ms}
                    totalMs={stored.response.timings.total_ms}
                  />
                </TraceSection>

                <TraceSection className="lg:col-span-1" delay={100}>
                  <TraceSectionTitle>Models & index</TraceSectionTitle>
                  <ModelsPanel trace={trace} />
                </TraceSection>

                {/* Row 3: latency spans 2, decisions/transcript fill the row */}
                <TraceSection className="lg:col-span-2" delay={140}>
                  <TraceSectionTitle>Latency</TraceSectionTitle>
                  <LatencyChart stages={trace.stages} />
                </TraceSection>

                <TraceSection className="lg:col-span-1" delay={180}>
                  <TraceSectionTitle>Decisions</TraceSectionTitle>
                  <DecisionPanel
                    guardrail={stored.response.guardrail}
                    crag={stored.response.crag}
                    abstentionReason={trace.abstention_reason}
                  />
                  {hasTranscript && stored.response.transcript && (
                    <div className="mt-5 border-t border-foreground/10 pt-5">
                      <TraceSectionTitle>Transcript</TraceSectionTitle>
                      <TranscriptPanel transcript={stored.response.transcript} />
                    </div>
                  )}
                </TraceSection>

                <TraceSection className="lg:col-span-3" delay={220}>
                  <TraceSectionTitle>Retrieval funnel</TraceSectionTitle>
                  <RetrievalFunnel
                    retrieved={trace.retrieved}
                    reranked={trace.reranked}
                    contexts={trace.contexts}
                    citedChunkIds={trace.cited_chunk_ids}
                  />
                </TraceSection>

                <TraceSection className="lg:col-span-1" delay={260}>
                  <TraceSectionTitle>Rerank scores</TraceSectionTitle>
                  <RankingChart ranked={trace.reranked} />
                </TraceSection>

                <TraceSection className="lg:col-span-2" delay={300}>
                  <TraceSectionTitle>Citations</TraceSectionTitle>
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
