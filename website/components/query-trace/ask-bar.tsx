"use client";

import { useState } from "react";
import { ArrowRight, Loader2 } from "lucide-react";

export function AskBar({
  busy,
  onAsk,
  autoFocus = false,
  size = "default",
}: {
  busy: boolean;
  onAsk: (question: string) => void;
  autoFocus?: boolean;
  size?: "default" | "large";
}) {
  const [question, setQuestion] = useState("");
  const submit = () => {
    const trimmed = question.trim();
    if (trimmed && !busy) onAsk(trimmed);
  };
  const large = size === "large";

  return (
    <form
      onSubmit={(event) => {
        event.preventDefault();
        submit();
      }}
      className={`flex w-full items-center rounded-full border border-foreground/15 bg-background/80 shadow-sm transition-colors focus-within:border-foreground/40 ${
        large ? "h-14 pl-6 pr-1.5" : "h-11 pl-5 pr-1"
      }`}
    >
      <label htmlFor="trace-ask" className="sr-only">
        Ask a question to trace
      </label>
      <input
        id="trace-ask"
        value={question}
        onChange={(event) => setQuestion(event.target.value)}
        disabled={busy}
        autoFocus={autoFocus}
        placeholder="Ask a question about FastRAG to trace it…"
        className={`min-w-0 flex-1 bg-transparent outline-none placeholder:text-muted-foreground disabled:opacity-60 ${
          large ? "text-base" : "text-sm"
        }`}
      />
      <button
        type="submit"
        disabled={busy || !question.trim()}
        aria-label="Trace this question"
        className={`flex shrink-0 items-center justify-center gap-2 rounded-full bg-foreground text-background transition-opacity hover:opacity-90 disabled:opacity-35 ${
          large ? "h-11 px-5 text-sm" : "h-9 w-9"
        }`}
      >
        {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <ArrowRight className="h-4 w-4" />}
        {large && <span>{busy ? "Tracing" : "Trace"}</span>}
      </button>
    </form>
  );
}
