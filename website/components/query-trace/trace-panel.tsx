import type { ReactNode } from "react";

/**
 * A titled band of the trace page. Bands are separated by hairlines, not boxed, so the page
 * reads as one document; `aside` holds a short figure or control on the title row.
 */
export function TracePanel({
  id,
  title,
  aside,
  children,
  className = "",
}: {
  id?: string;
  title: string;
  aside?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section id={id} className={`scroll-mt-28 border-t border-foreground/10 pt-6 pb-10 ${className}`}>
      <div className="mb-5 flex flex-wrap items-baseline justify-between gap-x-6 gap-y-1">
        <h2 className="font-display text-xl tracking-tight">{title}</h2>
        {aside && <div className="text-sm text-muted-foreground tabular-nums">{aside}</div>}
      </div>
      {children}
    </section>
  );
}
