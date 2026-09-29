"use client";

import { useEffect, useId, useState } from "react";
import { ArrowUpRight } from "lucide-react";

/**
 * Renders a ```mermaid block from the docs markdown. Mermaid is loaded on demand so pages
 * without diagrams do not pay for it; if it fails to parse, the source stays visible.
 * Wide diagrams fit the column inline, with a full-size view in a new tab for reading.
 */
export function MermaidDiagram({ chart }: { chart: string }) {
  const id = `mermaid-${useId().replace(/[^a-zA-Z0-9]/g, "")}`;
  const [svg, setSvg] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    import("mermaid")
      .then(async ({ default: mermaid }) => {
        mermaid.initialize({
          startOnLoad: false,
          theme: "neutral",
          securityLevel: "strict",
          fontFamily: "inherit",
        });
        const { svg: rendered } = await mermaid.render(id, chart);
        if (!cancelled) setSvg(rendered);
      })
      .catch(() => {
        if (!cancelled) setFailed(true);
      });
    return () => {
      cancelled = true;
    };
  }, [chart, id]);

  if (failed || svg === null) {
    return (
      <pre className="mb-6 overflow-x-auto rounded-xl border border-foreground/10 bg-foreground/[0.03] p-4">
        <code className="block font-mono text-sm leading-relaxed text-foreground/90">
          {failed ? chart : "Rendering diagram…"}
        </code>
      </pre>
    );
  }

  const openFullSize = () => {
    // Mermaid emits width="100%" plus a max-width, which would fit the new tab too; give the
    // standalone copy its natural size from the viewBox so it opens readable and scrollable.
    const [, , width = "0", height = "0"] =
      svg.match(/viewBox="([\d.\s-]+)"/)?.[1].trim().split(/\s+/) ?? [];
    const standalone = svg
      .replace(/max-width:\s*[\d.]+px;?/, "")
      .replace(/<svg([^>]*?)\swidth="100%"/, `<svg$1 width="${Math.ceil(Number(width))}" height="${Math.ceil(Number(height))}"`);
    const url = URL.createObjectURL(new Blob([standalone], { type: "image/svg+xml" }));
    window.open(url, "_blank", "noopener");
    setTimeout(() => URL.revokeObjectURL(url), 60_000);
  };

  return (
    <figure className="mb-6">
      <div
        className="overflow-x-auto rounded-xl border border-foreground/10 bg-background p-4 [&_svg]:mx-auto [&_svg]:h-auto"
        // Mermaid's own SVG output, sanitized by securityLevel "strict".
        dangerouslySetInnerHTML={{ __html: svg }}
      />
      <figcaption className="mt-2 flex justify-end">
        <button
          type="button"
          onClick={openFullSize}
          className="inline-flex items-center gap-1 text-sm text-muted-foreground underline underline-offset-4 decoration-foreground/30 hover:text-foreground"
        >
          Open full size
          <ArrowUpRight className="h-3.5 w-3.5" />
        </button>
      </figcaption>
    </figure>
  );
}
