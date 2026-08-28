"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { Navigation } from "@/components/landing/navigation";
import { FooterSection } from "@/components/landing/footer-section";
import { CitationsPanel } from "@/components/query-trace/citations-panel";
import { DecisionPanel, TranscriptPanel } from "@/components/query-trace/decision-panel";
import { LatencyChart } from "@/components/query-trace/latency-chart";
import { ModelsPanel } from "@/components/query-trace/models-panel";
import { PipelineConfigPanel } from "@/components/query-trace/pipeline-config-panel";
import { PipelineDiagram } from "@/components/query-trace/pipeline-diagram";
import { PipelineTimeline } from "@/components/query-trace/pipeline-timeline";
import { RankingChart } from "@/components/query-trace/ranking-chart";
import { RetrievalFunnel } from "@/components/query-trace/retrieval-funnel";
import { TraceHeader } from "@/components/query-trace/trace-header";
import { TraceSection, TraceSectionTitle } from "@/components/query-trace/trace-section";
import { textQuery } from "@/lib/api";
import {
  buildOverrides,
  friendlyQueryError,
  type PipelineConfigForm,
} from "@/lib/query-config";
import { loadLatestQueryTrace, saveQueryTrace, type StoredQueryTrace } from "@/lib/query-trace-store";
import type { QueryResponse } from "@/lib/types";

export default function QueryTracePage() {
  const [baseline, setBaseline] = useState<StoredQueryTrace | null>(null);
  const [active, setActive] = useState<StoredQueryTrace | null>(null);
  const [compareMode, setCompareMode] = useState<"active" | "baseline">("active");
  const [ready, setReady] = useState(false);
  const [busy, setBusy] = useState(false);
  const [preview, setPreview] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [formResetKey, setFormResetKey] = useState(0);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    const loaded = loadLatestQueryTrace();
    setBaseline(loaded);
    setActive(loaded);
    setReady(true);
    return () => abortRef.current?.abort();
  }, []);

  const displayed =
    compareMode === "baseline" && baseline ? baseline : active ?? baseline;
  const trace = displayed?.response.trace;
  const hasTranscript = Boolean(displayed?.response.transcript);
  const isRerunView = compareMode === "active" && active?.response.query_id !== baseline?.response.query_id;

  const handleRerun = useCallback(
    async (form: PipelineConfigForm) => {
      if (!active?.response.trace) return;
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;
      setBusy(true);
      setPreview("");
      setError(null);

      const originalTrace = baseline?.response.trace ?? active.response.trace;
      const overrides = buildOverrides(form, originalTrace);
      const documentIds =
        active.scopeMode === "document" && originalTrace.document_ids.length
          ? originalTrace.document_ids
          : undefined;

      try {
        await textQuery(
          active.question,
          {
            strategy: form.strategy !== originalTrace.strategy ? form.strategy : undefined,
            language: form.language || undefined,
            documentIds,
            overrides: Object.keys(overrides).length ? overrides : undefined,
          },
          {
            onChunk: (text) => setPreview((current) => (current ? `${current} ${text}` : text)),
            onFinal: (response: QueryResponse) => {
              const next: StoredQueryTrace = {
                question: active.question,
                response,
                savedAt: Date.now(),
                scopeMode: active.scopeMode,
                attachedCount: active.attachedCount,
              };
              saveQueryTrace(active.question, response, {
                scopeMode: active.scopeMode,
                attachedCount: active.attachedCount,
              });
              setActive(next);
              setCompareMode("active");
              setPreview(response.answer);
            },
            onError: (message) => setError(friendlyQueryError(message)),
          },
          controller.signal,
        );
      } catch (cause) {
        setError(friendlyQueryError(String(cause)));
      } finally {
        setBusy(false);
      }
    },
    [active, baseline],
  );

  const handleReset = useCallback(() => {
    abortRef.current?.abort();
    setBusy(false);
    setPreview("");
    setError(null);
    setActive(baseline);
    setCompareMode("baseline");
    setFormResetKey((key) => key + 1);
  }, [baseline]);

  return (
    <main className="relative min-h-screen overflow-x-hidden noise-overlay">
      <Navigation />
      <div className="pt-28 lg:pt-32 pb-16">
        <div className="mx-auto w-full max-w-[1440px] px-4 sm:px-6 lg:px-10">
          {!ready ? null : !baseline || !trace ? (
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
              <TraceHeader
                stored={displayed}
                response={displayed.response}
                compareMode={compareMode}
                hasBaseline={Boolean(baseline && active && baseline.response.query_id !== active.response.query_id)}
                onCompareModeChange={setCompareMode}
                isRerunView={isRerunView}
              />

              {baseline?.response.trace && (
                <PipelineConfigPanel
                  key={formResetKey}
                  baselineTrace={baseline.response.trace}
                  scopeMode={baseline.scopeMode}
                  documentIds={baseline.response.trace.document_ids}
                  busy={busy}
                  preview={preview}
                  onRerun={handleRerun}
                  onReset={handleReset}
                />
              )}

              {error && (
                <div className="mb-6 rounded-xl border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-900">
                  {error}
                </div>
              )}

              <div className="grid grid-cols-1 gap-4 lg:grid-cols-3 lg:gap-5 lg:auto-rows-min">
                <TraceSection className="lg:col-span-3" delay={0}>
                  <TraceSectionTitle>Path taken</TraceSectionTitle>
                  <PipelineDiagram
                    stages={trace.stages}
                    cacheStatus={displayed.response.cache_status}
                    outcome={displayed.response.outcome}
                  />
                </TraceSection>

                <TraceSection className="lg:col-span-2" delay={60}>
                  <TraceSectionTitle>Timeline</TraceSectionTitle>
                  <PipelineTimeline
                    stages={trace.stages}
                    generationMs={displayed.response.timings.generation_ms}
                    totalMs={displayed.response.timings.total_ms}
                  />
                </TraceSection>

                <TraceSection className="lg:col-span-1" delay={100}>
                  <TraceSectionTitle>Models & index</TraceSectionTitle>
                  <ModelsPanel trace={trace} />
                </TraceSection>

                <TraceSection className="lg:col-span-2" delay={140}>
                  <TraceSectionTitle>Latency</TraceSectionTitle>
                  <LatencyChart stages={trace.stages} />
                </TraceSection>

                <TraceSection className="lg:col-span-1" delay={180}>
                  <TraceSectionTitle>Decisions</TraceSectionTitle>
                  <DecisionPanel
                    guardrail={displayed.response.guardrail}
                    crag={displayed.response.crag}
                    abstentionReason={trace.abstention_reason}
                  />
                  {hasTranscript && displayed.response.transcript && (
                    <div className="mt-5 border-t border-foreground/10 pt-5">
                      <TraceSectionTitle>Transcript</TraceSectionTitle>
                      <TranscriptPanel transcript={displayed.response.transcript} />
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
                  <CitationsPanel citations={displayed.response.citations} />
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
