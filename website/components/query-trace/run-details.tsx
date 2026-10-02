"use client";

import { useState } from "react";
import { Check, Copy } from "lucide-react";
import type { QueryResponse } from "@/lib/types";
import { shortHash } from "@/lib/trace-format";
import { TracePanel } from "./trace-panel";

function CopyValue({ value, display }: { value: string; display: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      type="button"
      title={value}
      onClick={() => {
        void navigator.clipboard?.writeText(value).then(() => {
          setCopied(true);
          setTimeout(() => setCopied(false), 1200);
        });
      }}
      className="group inline-flex max-w-full items-center gap-1.5 text-right tabular-nums hover:text-foreground"
      aria-label={`Copy ${value}`}
    >
      <span className="truncate">{display}</span>
      {copied ? (
        <Check className="h-3 w-3 shrink-0 text-emerald-700" />
      ) : (
        <Copy className="h-3 w-3 shrink-0 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100 group-focus-visible:opacity-100" />
      )}
    </button>
  );
}

type Item = { label: string; value: string | null | undefined; hash?: boolean };

export function RunDetails({ response }: { response: QueryResponse }) {
  const trace = response.trace;
  if (!trace) return null;

  const groups: { title: string; items: Item[] }[] = [
    {
      title: "Run",
      items: [
        { label: "Profile", value: trace.profile },
        { label: "Strategy", value: trace.strategy },
        { label: "Language filter", value: trace.language ?? "any" },
        { label: "Cache", value: response.cache_status },
        { label: "Query id", value: response.query_id, hash: true },
        { label: "Trace id", value: response.trace_id, hash: true },
      ],
    },
    {
      title: "Index and models",
      items: [
        { label: "Collection", value: trace.collection_name },
        { label: "Content version", value: trace.content_version, hash: true },
        { label: "Embedder", value: trace.embedding_fingerprint, hash: true },
        { label: "Reranker", value: trace.reranker_fingerprint, hash: true },
        { label: "Generator", value: trace.generator_model },
        { label: "Speech to text", value: trace.stt_provider ? `${trace.stt_provider} · ${trace.stt_model}` : null },
      ],
    },
    {
      title: "Limits and thresholds",
      items: [
        { label: "Candidates (k)", value: String(trace.candidate_k) },
        { label: "Context chunks", value: String(trace.context_top_k) },
        { label: "Abstention gate", value: trace.reranker_threshold?.toFixed(3) },
        { label: "CRAG confident", value: trace.crag_confident_threshold?.toFixed(3) },
        { label: "Off-topic gate", value: trace.offtopic_threshold?.toFixed(3) },
      ],
    },
  ];

  const overrides = trace.overrides_applied;

  return (
    <TracePanel id="details" title="Run details">
      <div className="space-y-6">
        {groups.map((group) => (
          <dl key={group.title}>
            <p className="mb-1 text-xs text-muted-foreground">{group.title}</p>
            {group.items
              .filter((item) => item.value)
              .map((item) => (
                <div
                  key={item.label}
                  className="flex items-baseline justify-between gap-4 border-b border-foreground/[0.06] py-1.5 text-sm last:border-0"
                >
                  <dt className="shrink-0 text-muted-foreground">{item.label}</dt>
                  <dd className="min-w-0 text-right">
                    {item.hash ? (
                      <CopyValue value={item.value!} display={shortHash(item.value)} />
                    ) : (
                      <span className="break-words tabular-nums">{item.value}</span>
                    )}
                  </dd>
                </div>
              ))}
          </dl>
        ))}
        {overrides && Object.keys(overrides).length > 0 && (
          <div>
            <p className="mb-1 text-xs text-muted-foreground">Overrides applied</p>
            <pre className="overflow-x-auto rounded-[2px] bg-foreground/[0.03] p-3 font-mono text-xs leading-relaxed">
              {JSON.stringify(overrides, null, 2)}
            </pre>
          </div>
        )}
      </div>
    </TracePanel>
  );
}
