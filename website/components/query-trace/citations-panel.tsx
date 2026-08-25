import type { Citation } from "@/lib/types";

export function CitationsPanel({ citations }: { citations: Citation[] }) {
  if (!citations.length) {
    return <p className="text-sm text-muted-foreground">No citations in the final answer.</p>;
  }

  return (
    <ol className="space-y-4">
      {citations.map((citation) => (
        <li key={citation.chunk_id} className="rounded-lg border border-foreground/10 p-4">
          <div className="flex items-start gap-3">
            <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full border border-foreground/20 font-mono text-xs">
              {citation.number}
            </span>
            <div className="min-w-0 space-y-1">
              <p className="font-medium">{citation.title}</p>
              <p className="font-mono text-[10px] text-muted-foreground break-all">{citation.chunk_id}</p>
              <p className="text-sm text-muted-foreground leading-relaxed">{citation.excerpt}</p>
            </div>
          </div>
        </li>
      ))}
    </ol>
  );
}
