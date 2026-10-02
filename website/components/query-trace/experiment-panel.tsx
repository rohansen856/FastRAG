"use client";

import { useEffect, useState } from "react";
import { ChevronDown, Loader2, Play, RotateCcw } from "lucide-react";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { fetchStrategies } from "@/lib/api";
import {
  buildOverrides,
  configFromTrace,
  LANGUAGES,
  type PipelineConfigForm,
} from "@/lib/query-config";
import type { QueryTrace } from "@/lib/types";

function Group({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div role="group" aria-label={title} className="space-y-3 border-t border-foreground/10 pt-4">
      <p className="text-xs text-muted-foreground">{title}</p>
      {children}
    </div>
  );
}

function Field({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <label className="block space-y-1.5">
      <span className="text-sm">{label}</span>
      {children}
      {hint && <span className="block text-xs leading-relaxed text-muted-foreground">{hint}</span>}
    </label>
  );
}

function Toggle({
  label,
  hint,
  checked,
  onChange,
}: {
  label: string;
  hint: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
}) {
  return (
    <div className="flex items-center justify-between gap-4">
      <div>
        <p className="text-sm">{label}</p>
        <p className="text-xs text-muted-foreground">{hint}</p>
      </div>
      <Switch checked={checked} onCheckedChange={onChange} aria-label={label} />
    </div>
  );
}

function Threshold({
  label,
  value,
  min,
  onChange,
}: {
  label: string;
  value: string;
  min: number;
  onChange: (value: string) => void;
}) {
  return (
    <label className="block">
      <span className="flex items-baseline justify-between text-sm">
        {label}
        <span className="text-xs text-muted-foreground tabular-nums">{Number(value).toFixed(2)}</span>
      </span>
      <input
        type="range"
        min={min}
        max={1}
        step={0.01}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="mt-1 w-full accent-foreground"
      />
    </label>
  );
}

/**
 * Per-request overrides for a re-run of the same question. Only changed fields are sent;
 * the server applies them when FASTRAG_ALLOW_QUERY_OVERRIDES allows it.
 */
export function ExperimentPanel({
  baselineTrace,
  scopeMode,
  busy,
  preview,
  error,
  hasRerun,
  onRerun,
  onReset,
}: {
  baselineTrace: QueryTrace;
  scopeMode?: "document" | "corpus";
  busy: boolean;
  preview: string;
  error: string | null;
  hasRerun: boolean;
  onRerun: (form: PipelineConfigForm) => void;
  onReset: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [strategies, setStrategies] = useState<string[]>([baselineTrace.strategy || "sentence"]);
  const [form, setForm] = useState<PipelineConfigForm>(() =>
    configFromTrace(baselineTrace, baselineTrace.strategy || "sentence"),
  );

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    fetchStrategies()
      .then((payload) => {
        if (cancelled) return;
        const list = payload.indexed.length ? payload.indexed : payload.available;
        setStrategies(list.includes(baselineTrace.strategy) ? list : [baselineTrace.strategy, ...list]);
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [open, baselineTrace.strategy]);

  const patch = (partial: Partial<PipelineConfigForm>) => setForm((current) => ({ ...current, ...partial }));
  const changes = Object.entries(buildOverrides(form, baselineTrace));
  const strategyChanged = form.strategy !== baselineTrace.strategy;
  const languageChanged = form.language !== (baselineTrace.language ?? "");
  const changeCount = changes.length + Number(strategyChanged) + Number(languageChanged);

  return (
    <section id="experiment" className="scroll-mt-28 border-t border-foreground/10 pt-6 pb-10">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
        className="flex w-full items-baseline justify-between gap-4 text-left"
      >
        <span>
          <span className="block font-display text-xl tracking-tight">Experiment</span>
          <span className="mt-1 block text-sm text-muted-foreground">
            Change the pipeline settings and re-run this question.
          </span>
        </span>
        <ChevronDown
          className={`h-5 w-5 shrink-0 self-center text-muted-foreground transition-transform duration-200 ${open ? "rotate-180" : ""}`}
        />
      </button>

      {open && (
        <div className="mt-5 space-y-5">
          <Group title="Retrieval">
            <Field label="Chunking strategy">
              <Select value={form.strategy} onValueChange={(value) => patch({ strategy: value })}>
                <SelectTrigger className="w-full">
                  <SelectValue placeholder="Strategy" />
                </SelectTrigger>
                <SelectContent>
                  {strategies.map((strategy) => (
                    <SelectItem key={strategy} value={strategy}>
                      {strategy}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </Field>
            <Field label="Language filter">
              <Select
                value={form.language || "auto"}
                onValueChange={(value) => patch({ language: value === "auto" ? "" : value })}
              >
                <SelectTrigger className="w-full">
                  <SelectValue placeholder="Language" />
                </SelectTrigger>
                <SelectContent>
                  {LANGUAGES.map((lang) => (
                    <SelectItem key={lang.code || "auto"} value={lang.code || "auto"}>
                      {lang.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </Field>
            <div className="grid grid-cols-2 gap-3">
              <Field label="Candidates">
                <Input
                  type="number"
                  min={1}
                  max={100}
                  value={form.candidateK}
                  onChange={(event) => patch({ candidateK: event.target.value })}
                />
              </Field>
              <Field label="Context chunks">
                <Input
                  type="number"
                  min={1}
                  max={20}
                  value={form.contextTopK}
                  onChange={(event) => patch({ contextTopK: event.target.value })}
                />
              </Field>
            </div>
            <p className="text-xs text-muted-foreground">
              Scope: {scopeMode === "document" ? "the attached files from the original run" : "the whole corpus"}.
            </p>
          </Group>

          <Group title="Gates">
            <Toggle
              label="Skip cache"
              hint="Bypass the exact and semantic cache"
              checked={form.skipCache}
              onChange={(checked) => patch({ skipCache: checked })}
            />
            <Toggle
              label="CRAG"
              hint="Grade retrieval and refine or rewrite"
              checked={form.cragEnabled}
              onChange={(checked) => patch({ cragEnabled: checked })}
            />
            <Threshold
              label="Abstention gate"
              value={form.rerankerThreshold}
              min={0}
              onChange={(value) => patch({ rerankerThreshold: value })}
            />
            <Threshold
              label="CRAG confident"
              value={form.cragConfidentThreshold}
              min={0}
              onChange={(value) => patch({ cragConfidentThreshold: value })}
            />
            <Threshold
              label="Off-topic gate"
              value={form.offtopicThreshold}
              min={-1}
              onChange={(value) => patch({ offtopicThreshold: value })}
            />
          </Group>

          <Group title="Model">
            <Field label="Model">
              <Input
                value={form.llmModel}
                onChange={(event) => patch({ llmModel: event.target.value })}
                placeholder={baselineTrace.generator_model ?? "Server default"}
              />
            </Field>
            <Field label="Base URL" hint="Empty uses the server's endpoint.">
              <Input
                value={form.llmBaseUrl}
                onChange={(event) => patch({ llmBaseUrl: event.target.value })}
                placeholder="https://api.openai.com/v1"
              />
            </Field>
            <Field label="API key" hint="Sent with this re-run only, and never stored in the trace.">
              <Input
                type="password"
                value={form.llmApiKey}
                onChange={(event) => patch({ llmApiKey: event.target.value })}
                placeholder="Only for another endpoint"
                autoComplete="off"
              />
            </Field>
            <Field label="Max tokens">
              <Input
                type="number"
                min={1}
                value={form.llmMaxTokens}
                onChange={(event) => patch({ llmMaxTokens: event.target.value })}
                placeholder="Server default"
              />
            </Field>
          </Group>

          {error && (
            <p role="alert" className="border-t border-foreground/10 pt-4 text-sm text-rose-700">
              {error}
            </p>
          )}

          {preview && (
            <div className="border-t border-foreground/10 pt-4">
              <p className="text-xs text-muted-foreground">Streaming</p>
              <p className="mt-1 text-sm leading-relaxed">{preview}</p>
            </div>
          )}

          <div className="flex flex-wrap items-center gap-3 border-t border-foreground/10 pt-4">
            <button
              type="button"
              onClick={() => onRerun(form)}
              disabled={busy}
              className="inline-flex items-center gap-2 rounded-full bg-foreground px-4 py-2 text-sm text-background transition-opacity hover:opacity-90 disabled:opacity-50"
            >
              {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-3.5 w-3.5 fill-current" />}
              {busy ? "Running" : "Re-run"}
            </button>
            {hasRerun && (
              <button
                type="button"
                onClick={() => {
                  setForm(configFromTrace(baselineTrace, baselineTrace.strategy || "sentence"));
                  onReset();
                }}
                disabled={busy}
                className="inline-flex items-center gap-2 rounded-full border border-foreground/20 px-4 py-2 text-sm transition-colors hover:border-foreground disabled:opacity-50"
              >
                <RotateCcw className="h-3.5 w-3.5" />
                Back to original
              </button>
            )}
            <span className="text-xs text-muted-foreground tabular-nums">
              {changeCount ? `${changeCount} change${changeCount === 1 ? "" : "s"}` : "No changes yet"}
            </span>
          </div>
        </div>
      )}
    </section>
  );
}
