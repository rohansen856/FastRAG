"use client";

import { useState } from "react";
import { ChevronDown } from "lucide-react";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { QUERY_EXAMPLES, type QueryExampleSlug } from "@/lib/query-examples";
import type { StoredQueryTrace } from "@/lib/query-trace-store";
import { OutcomeDot } from "./outcome-dot";

export type RunChoice = { kind: "session"; queryId: string } | { kind: "example"; slug: QueryExampleSlug };

const EXAMPLE_OUTCOME = { answered: "answered", abstained: "no_answer", refused: "refused" } as const;

function timeLabel(savedAt: number): string {
  return new Date(savedAt).toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
}

export function RunsMenu({
  sessionRuns,
  current,
  onChoose,
}: {
  sessionRuns: StoredQueryTrace[];
  current: RunChoice | null;
  onChoose: (choice: RunChoice) => void;
}) {
  const [open, setOpen] = useState(false);
  const choose = (choice: RunChoice) => {
    setOpen(false);
    onChoose(choice);
  };
  const itemClass = (selected: boolean) =>
    `flex w-full items-start gap-3 rounded-[2px] px-3 py-2 text-left text-sm transition-colors ${
      selected ? "bg-foreground/[0.06]" : "hover:bg-foreground/[0.04]"
    }`;

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <button
          type="button"
          className="inline-flex h-11 shrink-0 items-center gap-2 rounded-full border border-foreground/15 px-4 text-sm transition-colors hover:border-foreground/40"
        >
          Runs
          <span className="text-xs text-muted-foreground tabular-nums">
            {sessionRuns.length + QUERY_EXAMPLES.length}
          </span>
          <ChevronDown className="h-4 w-4 text-muted-foreground" />
        </button>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-[min(26rem,calc(100vw-2rem))] rounded-[2px] p-2">
        {sessionRuns.length > 0 && (
          <div className="mb-2">
            <p className="px-3 pb-1 pt-1 text-xs text-muted-foreground">This session</p>
            {sessionRuns.map((run) => {
              const selected = current?.kind === "session" && current.queryId === run.response.query_id;
              return (
                <button
                  key={run.response.query_id}
                  type="button"
                  onClick={() => choose({ kind: "session", queryId: run.response.query_id })}
                  className={itemClass(selected)}
                >
                  <OutcomeDot outcome={run.response.outcome} className="mt-1.5" />
                  <span className="min-w-0 flex-1 truncate">{run.question}</span>
                  <span className="shrink-0 text-xs text-muted-foreground tabular-nums">
                    {timeLabel(run.savedAt)}
                  </span>
                </button>
              );
            })}
          </div>
        )}
        <p className="px-3 pb-1 pt-1 text-xs text-muted-foreground">Recorded examples</p>
        {QUERY_EXAMPLES.map((example) => {
          const selected = current?.kind === "example" && current.slug === example.slug;
          return (
            <button
              key={example.slug}
              type="button"
              onClick={() => choose({ kind: "example", slug: example.slug })}
              className={itemClass(selected)}
            >
              <OutcomeDot outcome={EXAMPLE_OUTCOME[example.slug]} className="mt-1.5" />
              <span className="min-w-0 flex-1">
                <span className="block truncate">{example.question}</span>
                <span className="block text-xs text-muted-foreground">{example.summary}</span>
              </span>
            </button>
          );
        })}
      </PopoverContent>
    </Popover>
  );
}
