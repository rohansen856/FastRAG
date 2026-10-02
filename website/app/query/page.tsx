"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Navigation } from "@/components/landing/navigation";
import { FooterSection } from "@/components/landing/footer-section";
import { AnswerPanel } from "@/components/query-trace/answer-panel";
import { AskBar } from "@/components/query-trace/ask-bar";
import { DecisionPanel } from "@/components/query-trace/decision-panel";
import { EvidencePanel } from "@/components/query-trace/evidence-panel";
import { ExperimentPanel } from "@/components/query-trace/experiment-panel";
import { OutcomeDot } from "@/components/query-trace/outcome-dot";
import { RunDetails } from "@/components/query-trace/run-details";
import { RunsMenu, type RunChoice } from "@/components/query-trace/runs-menu";
import { StageWaterfall } from "@/components/query-trace/stage-waterfall";
import { TraceHeader } from "@/components/query-trace/trace-header";
import { TracePanel } from "@/components/query-trace/trace-panel";
import { textQuery } from "@/lib/api";
import { buildOverrides, friendlyQueryError, type PipelineConfigForm } from "@/lib/query-config";
import { isExampleSlug, loadQueryExample, QUERY_EXAMPLES } from "@/lib/query-examples";
import {
  listRecentTraces,
  loadQueryTrace,
  saveQueryTrace,
  type StoredQueryTrace,
} from "@/lib/query-trace-store";
import type { QueryResponse } from "@/lib/types";

const EXAMPLE_OUTCOME = { answered: "answered", abstained: "no_answer", refused: "refused" } as const;

function setExampleParam(slug: string | null) {
  const url = new URL(window.location.href);
  if (slug) url.searchParams.set("example", slug);
  else url.searchParams.delete("example");
  window.history.replaceState(null, "", url);
}

/** Shown while a fresh question streams in: the answer as it arrives, the rest as placeholders. */
function PendingRun({ question, preview }: { question: string; preview: string }) {
  return (
    <>
      <header className="pb-10 pt-10 lg:pt-14">
        <h1 className="max-w-[28ch] text-balance font-display text-3xl leading-[1.1] tracking-tight lg:text-5xl">
          {question}
        </h1>
        <p className="mt-5 text-lg text-muted-foreground">Tracing the pipeline…</p>
      </header>
      <TracePanel title="Answer">
        {preview ? (
          <p className="max-w-[68ch] text-lg leading-relaxed">
            {preview}
            <span className="ml-0.5 inline-block h-4 w-0.5 animate-pulse bg-foreground align-middle" />
          </p>
        ) : (
          <div className="max-w-[68ch] space-y-3" aria-label="Waiting for the first sentence">
            {[100, 92, 64].map((width) => (
              <span
                key={width}
                className="block h-4 animate-pulse rounded-[2px] bg-foreground/[0.06]"
                style={{ width: `${width}%` }}
              />
            ))}
          </div>
        )}
      </TracePanel>
    </>
  );
}

function StartHere({
  busy,
  onAsk,
  onExample,
}: {
  busy: boolean;
  onAsk: (question: string) => void;
  onExample: (choice: RunChoice) => void;
}) {
  return (
    <div className="grid gap-16 pb-16 pt-10 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)] lg:gap-24 lg:pt-16">
      <div>
        <h1 className="max-w-[16ch] text-balance font-display text-4xl leading-[1.05] tracking-tight lg:text-6xl">
          Follow one question through the pipeline.
        </h1>
        <p className="mt-6 max-w-[52ch] text-lg leading-relaxed text-muted-foreground">
          Ask something and see every stage it passed: guardrails, cache, retrieval, rerank, the
          CRAG gate and generation, with timings, scores and the sources it cited.
        </p>
        <div className="mt-10 max-w-xl">
          <AskBar busy={busy} onAsk={onAsk} size="large" autoFocus />
        </div>
      </div>

      <div className="lg:pt-3">
        <p className="text-sm text-muted-foreground">Or open a recorded run</p>
        <ul className="mt-3 border-t border-foreground/10">
          {QUERY_EXAMPLES.map((example) => (
            <li key={example.slug} className="border-b border-foreground/10">
              <button
                type="button"
                onClick={() => onExample({ kind: "example", slug: example.slug })}
                className="group flex w-full items-start gap-4 py-5 text-left"
              >
                <OutcomeDot outcome={EXAMPLE_OUTCOME[example.slug]} className="mt-2" />
                <span className="min-w-0 flex-1">
                  <span className="block text-lg leading-snug underline decoration-transparent underline-offset-4 transition-colors group-hover:decoration-foreground/30">
                    {example.question}
                  </span>
                  <span className="mt-1 block text-sm text-muted-foreground">{example.summary}</span>
                </span>
              </button>
            </li>
          ))}
        </ul>
        <p className="mt-4 text-xs leading-relaxed text-muted-foreground">
          Recorded from the hosted API on the cloud profile. Runs you trace here are kept in this
          browser tab only.
        </p>
      </div>
    </div>
  );
}

export default function QueryTracePage() {
  const [ready, setReady] = useState(false);
  const [baseline, setBaseline] = useState<StoredQueryTrace | null>(null);
  const [active, setActive] = useState<StoredQueryTrace | null>(null);
  const [current, setCurrent] = useState<RunChoice | null>(null);
  const [compareMode, setCompareMode] = useState<"active" | "baseline">("active");
  const [sessionRuns, setSessionRuns] = useState<StoredQueryTrace[]>([]);
  const [pending, setPending] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [preview, setPreview] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [rerunError, setRerunError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const show = useCallback((run: StoredQueryTrace, choice: RunChoice) => {
    abortRef.current?.abort();
    setBaseline(run);
    setActive(run);
    setCurrent(choice);
    setCompareMode("active");
    setPreview("");
    setError(null);
    setRerunError(null);
    setExampleParam(choice.kind === "example" ? choice.slug : null);
  }, []);

  const choose = useCallback(
    async (choice: RunChoice) => {
      if (choice.kind === "session") {
        const run = loadQueryTrace(choice.queryId);
        if (run) show(run, choice);
        return;
      }
      try {
        show(await loadQueryExample(choice.slug), choice);
      } catch (cause) {
        setError(friendlyQueryError(String(cause)));
      }
    },
    [show],
  );

  useEffect(() => {
    const runs = listRecentTraces();
    setSessionRuns(runs);
    const param = new URL(window.location.href).searchParams.get("example");
    const start = isExampleSlug(param)
      ? choose({ kind: "example", slug: param })
      : runs[0]
        ? choose({ kind: "session", queryId: runs[0].response.query_id })
        : Promise.resolve();
    void start.finally(() => setReady(true));
    return () => abortRef.current?.abort();
  }, [choose]);

  const runQuery = useCallback(
    async (question: string, form?: PipelineConfigForm) => {
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;
      setBusy(true);
      setPreview("");
      setError(null);
      setRerunError(null);

      const base = form ? baseline : null;
      const baseTrace = base?.response.trace;
      const overrides = form && baseTrace ? buildOverrides(form, baseTrace) : {};
      const documentIds =
        base?.scopeMode === "document" && baseTrace?.document_ids.length ? baseTrace.document_ids : undefined;
      const meta = { scopeMode: base?.scopeMode ?? ("corpus" as const), attachedCount: base?.attachedCount };
      if (!form) setPending(question);

      try {
        await textQuery(
          question,
          {
            strategy: form && baseTrace && form.strategy !== baseTrace.strategy ? form.strategy : undefined,
            language: form?.language || undefined,
            documentIds,
            overrides: Object.keys(overrides).length ? overrides : undefined,
          },
          {
            onChunk: (text) => setPreview((value) => (value ? `${value} ${text}` : text)),
            onFinal: (response: QueryResponse) => {
              saveQueryTrace(question, response, meta);
              const run: StoredQueryTrace = { question, response, savedAt: Date.now(), ...meta };
              setSessionRuns(listRecentTraces());
              if (form) {
                setActive(run);
                setCompareMode("active");
              } else {
                show(run, { kind: "session", queryId: response.query_id });
              }
            },
            onError: (message) => (form ? setRerunError : setError)(friendlyQueryError(message)),
          },
          controller.signal,
        );
      } catch (cause) {
        if (!controller.signal.aborted) (form ? setRerunError : setError)(friendlyQueryError(String(cause)));
      } finally {
        if (abortRef.current === controller) {
          setBusy(false);
          setPending(null);
        }
      }
    },
    [baseline, show],
  );

  const displayed = compareMode === "baseline" ? baseline : active;
  const hasRerun = Boolean(baseline && active && baseline.response.query_id !== active.response.query_id);
  const response = displayed?.response;

  return (
    <main className="relative min-h-screen overflow-x-hidden noise-overlay selection:bg-foreground selection:text-background">
      <Navigation />
      <div className="mx-auto w-full max-w-[1400px] px-6 pt-28 lg:px-12 lg:pt-32">
        {(displayed || pending) && (
          <div className="flex items-center gap-3 border-b border-foreground/10 pb-5">
            <div className="min-w-0 flex-1">
              <AskBar busy={busy} onAsk={(question) => void runQuery(question)} />
            </div>
            <RunsMenu sessionRuns={sessionRuns} current={current} onChoose={(choice) => void choose(choice)} />
          </div>
        )}

        {error && (
          <p role="alert" className="mt-5 text-sm text-rose-700">
            {error}
          </p>
        )}

        {!ready ? (
          <div className="h-[60vh]" />
        ) : pending ? (
          <PendingRun question={pending} preview={preview} />
        ) : !displayed || !response ? (
          <StartHere busy={busy} onAsk={(question) => void runQuery(question)} onExample={(choice) => void choose(choice)} />
        ) : (
          <div>
            <TraceHeader
              run={displayed}
              example={current?.kind === "example" && displayed === baseline}
              compare={hasRerun ? { mode: compareMode, onChange: setCompareMode } : undefined}
            />

            <div className="grid gap-x-16 pb-16 xl:grid-cols-[minmax(0,1fr)_22rem]">
              <div className="min-w-0">
                <AnswerPanel response={response} />
                <div className="xl:hidden">
                  <DecisionPanel response={response} />
                </div>
                <StageWaterfall response={response} />
                <EvidencePanel key={response.query_id} response={response} />
              </div>
              <aside className="min-w-0">
                <div className="hidden xl:block">
                  <DecisionPanel response={response} />
                </div>
                <RunDetails response={response} />
                {baseline?.response.trace && response.outcome !== "refused" && (
                  <ExperimentPanel
                    key={baseline.response.query_id}
                    baselineTrace={baseline.response.trace}
                    scopeMode={baseline.scopeMode}
                    busy={busy}
                    preview={pending ? "" : preview}
                    error={rerunError}
                    hasRerun={hasRerun}
                    onRerun={(form) => void runQuery(baseline.question, form)}
                    onReset={() => setCompareMode("baseline")}
                  />
                )}
              </aside>
            </div>
          </div>
        )}
      </div>
      <FooterSection />
    </main>
  );
}
