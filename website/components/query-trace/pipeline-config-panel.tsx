"use client";

import { ChevronDown, Play, RotateCcw } from "lucide-react";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
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

function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-1.5">
      <Label className="text-xs font-mono uppercase tracking-widest text-muted-foreground">
        {label}
      </Label>
      {children}
      {hint && <p className="text-xs text-muted-foreground leading-relaxed">{hint}</p>}
    </div>
  );
}

export function PipelineConfigPanel({
  baselineTrace,
  scopeMode,
  documentIds,
  busy,
  preview,
  onRerun,
  onReset,
}: {
  baselineTrace: QueryTrace;
  scopeMode?: "document" | "corpus";
  documentIds: string[];
  busy: boolean;
  preview: string;
  onRerun: (form: PipelineConfigForm) => void;
  onReset: () => void;
}) {
  const [open, setOpen] = useState(true);
  const [strategies, setStrategies] = useState<string[]>(["sentence"]);
  const [defaultStrategy, setDefaultStrategy] = useState("sentence");
  const [form, setForm] = useState<PipelineConfigForm>(() =>
    configFromTrace(baselineTrace, "sentence"),
  );

  useEffect(() => {
    fetchStrategies()
      .then((payload) => {
        const list = payload.indexed.length ? payload.indexed : payload.available;
        setStrategies(list);
        setDefaultStrategy(payload.default);
        setForm(configFromTrace(baselineTrace, payload.default));
      })
      .catch(() => setForm(configFromTrace(baselineTrace, defaultStrategy)));
  }, [baselineTrace, defaultStrategy]);

  const patch = (partial: Partial<PipelineConfigForm>) =>
    setForm((current) => ({ ...current, ...partial }));

  const overridesPreview = buildOverrides(form, baselineTrace);

  return (
    <Collapsible open={open} onOpenChange={setOpen} className="mb-8">
      <div className="rounded-2xl border border-foreground/10 bg-foreground/[0.02]">
        <CollapsibleTrigger className="flex w-full items-center justify-between gap-4 px-5 py-4 text-left">
          <div>
            <p className="text-sm font-mono uppercase tracking-widest text-muted-foreground">
              Experiment
            </p>
            <p className="text-base font-display mt-1">Edit pipeline config and re-run</p>
          </div>
          <ChevronDown
            className={`h-5 w-5 shrink-0 text-muted-foreground transition-transform ${open ? "rotate-180" : ""}`}
          />
        </CollapsibleTrigger>

        <CollapsibleContent className="border-t border-foreground/10 px-5 pb-5 pt-4">
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
            <div className="space-y-4">
              <p className="text-xs font-mono uppercase tracking-widest text-muted-foreground">
                Retrieval
              </p>
              <Field label="Strategy">
                <Select value={form.strategy} onValueChange={(value) => patch({ strategy: value })}>
                  <SelectTrigger>
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
                  <SelectTrigger>
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
              <Field label="Scope" hint="Document scope from the original run.">
                <div className="rounded-lg border border-foreground/10 px-3 py-2 text-sm font-mono">
                  {scopeMode === "document"
                    ? documentIds.length
                      ? `${documentIds.length} attached doc(s)`
                      : "Attached (ids unavailable)"
                    : "Full corpus"}
                </div>
              </Field>
            </div>

            <div className="space-y-4">
              <p className="text-xs font-mono uppercase tracking-widest text-muted-foreground">
                Pipeline
              </p>
              <div className="flex items-center justify-between gap-4 rounded-lg border border-foreground/10 px-3 py-2">
                <div>
                  <p className="text-sm font-medium">Skip cache</p>
                  <p className="text-xs text-muted-foreground">Bypass exact and semantic cache</p>
                </div>
                <Switch checked={form.skipCache} onCheckedChange={(checked) => patch({ skipCache: checked })} />
              </div>
              <div className="flex items-center justify-between gap-4 rounded-lg border border-foreground/10 px-3 py-2">
                <div>
                  <p className="text-sm font-medium">CRAG</p>
                  <p className="text-xs text-muted-foreground">Corrective retrieval grading</p>
                </div>
                <Switch
                  checked={form.cragEnabled}
                  onCheckedChange={(checked) => patch({ cragEnabled: checked })}
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <Field label="Candidate K">
                  <Input
                    type="number"
                    min={1}
                    max={100}
                    value={form.candidateK}
                    onChange={(event) => patch({ candidateK: event.target.value })}
                  />
                </Field>
                <Field label="Context top K">
                  <Input
                    type="number"
                    min={1}
                    max={20}
                    value={form.contextTopK}
                    onChange={(event) => patch({ contextTopK: event.target.value })}
                  />
                </Field>
              </div>
              <div className="space-y-3">
                <Field label={`Rerank threshold (${form.rerankerThreshold})`}>
                  <input
                    type="range"
                    min={0}
                    max={1}
                    step={0.01}
                    value={form.rerankerThreshold}
                    onChange={(event) => patch({ rerankerThreshold: event.target.value })}
                    className="w-full accent-foreground"
                  />
                </Field>
                <Field label={`CRAG confident (${form.cragConfidentThreshold})`}>
                  <input
                    type="range"
                    min={0}
                    max={1}
                    step={0.01}
                    value={form.cragConfidentThreshold}
                    onChange={(event) => patch({ cragConfidentThreshold: event.target.value })}
                    className="w-full accent-foreground"
                  />
                </Field>
                <Field label={`Off-topic (${form.offtopicThreshold})`}>
                  <input
                    type="range"
                    min={-1}
                    max={1}
                    step={0.01}
                    value={form.offtopicThreshold}
                    onChange={(event) => patch({ offtopicThreshold: event.target.value })}
                    className="w-full accent-foreground"
                  />
                </Field>
              </div>
            </div>

            <div className="space-y-4">
              <p className="text-xs font-mono uppercase tracking-widest text-muted-foreground">LLM</p>
              <Field label="Model">
                <Input
                  value={form.llmModel}
                  onChange={(event) => patch({ llmModel: event.target.value })}
                  placeholder={baselineTrace.generator_model ?? "Server default"}
                />
              </Field>
              <Field label="Base URL" hint="Leave empty to use the server default endpoint.">
                <Input
                  value={form.llmBaseUrl}
                  onChange={(event) => patch({ llmBaseUrl: event.target.value })}
                  placeholder="https://api.openai.com/v1"
                />
              </Field>
              <Field label="API key" hint="Sent only for this re-run; never stored in the trace.">
                <Input
                  type="password"
                  value={form.llmApiKey}
                  onChange={(event) => patch({ llmApiKey: event.target.value })}
                  placeholder="Optional override"
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
            </div>
          </div>

          {Object.keys(overridesPreview).length > 0 && (
            <div className="mt-5 flex flex-wrap gap-2">
              {Object.entries(overridesPreview).map(([key, value]) => (
                <span
                  key={key}
                  className="rounded-full border border-foreground/15 px-2.5 py-0.5 text-xs font-mono text-muted-foreground"
                >
                  {key}
                  {typeof value === "object" ? `: ${JSON.stringify(value)}` : `: ${String(value)}`}
                </span>
              ))}
            </div>
          )}

          {preview && (
            <div className="mt-5 rounded-xl border border-foreground/10 bg-background/60 px-4 py-3">
              <p className="text-xs font-mono uppercase tracking-widest text-muted-foreground mb-2">
                Live preview
              </p>
              <p className="text-sm leading-relaxed whitespace-pre-wrap">{preview}</p>
            </div>
          )}

          <div className="mt-5 flex flex-wrap gap-3">
            <Button onClick={() => onRerun(form)} disabled={busy} className="gap-2">
              <Play className="h-4 w-4" />
              {busy ? "Running…" : "Re-run pipeline"}
            </Button>
            <Button type="button" variant="outline" onClick={onReset} disabled={busy} className="gap-2">
              <RotateCcw className="h-4 w-4" />
              Reset to original
            </Button>
          </div>
        </CollapsibleContent>
      </div>
    </Collapsible>
  );
}
