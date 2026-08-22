const GITHUB_URL = "https://github.com/rohansen856/FastRAG";

export type DocPage = {
  slug: string;
  title: string;
  file: string;
  description: string;
};

export const DOC_SECTIONS: { label: string; pages: DocPage[] }[] = [
  {
    label: "Getting started",
    pages: [
      {
        slug: "running-locally",
        title: "Running locally",
        file: "local-setup.md",
        description: "Compose stack, profiles, calibration, and first query.",
      },
      {
        slug: "deployment",
        title: "Deployment",
        file: "deployment.md",
        description: "Vercel, Render, env vars, and cloud providers.",
      },
      {
        slug: "providers",
        title: "Providers",
        file: "providers.md",
        description: "Local vs cloud adapter matrix.",
      },
    ],
  },
  {
    label: "Architecture",
    pages: [
      {
        slug: "architecture",
        title: "Architecture",
        file: "architecture.md",
        description: "Request path, components, and data flow.",
      },
    ],
  },
  {
    label: "Pipeline",
    pages: [
      {
        slug: "chunking",
        title: "Chunking",
        file: "chunking.md",
        description: "Strategies, metadata, and index shape.",
      },
      {
        slug: "crag",
        title: "CRAG",
        file: "crag.md",
        description: "Corrective retrieval grading and rewrite.",
      },
      {
        slug: "guardrails",
        title: "Guardrails",
        file: "guardrails.md",
        description: "Input gates before retrieval and generation.",
      },
      {
        slug: "voice",
        title: "Voice",
        file: "voice.md",
        description: "STT, streaming voice queries, and audio handling.",
      },
      {
        slug: "latency",
        title: "Latency",
        file: "latency.md",
        description: "Stage budgets and the sub-200ms retrieval target.",
      },
    ],
  },
  {
    label: "Operations",
    pages: [
      {
        slug: "operations",
        title: "Operations",
        file: "operations.md",
        description: "Monitoring, tracing, and day-two tasks.",
      },
      {
        slug: "runbook",
        title: "Runbook",
        file: "runbook.md",
        description: "Incident checks and recovery steps.",
      },
      {
        slug: "benchmarking",
        title: "Benchmarking",
        file: "benchmarking.md",
        description: "Latency harness and golden gates.",
      },
      {
        slug: "llm-providers",
        title: "LLM providers",
        file: "llm-providers.md",
        description: "OpenAI-compatible generation backends.",
      },
    ],
  },
];

export const ALL_DOC_PAGES = DOC_SECTIONS.flatMap((section) => section.pages);

const FILE_TO_SLUG = Object.fromEntries(ALL_DOC_PAGES.map((page) => [page.file, page.slug]));

export function getDocBySlug(slug: string): DocPage | undefined {
  return ALL_DOC_PAGES.find((page) => page.slug === slug);
}

/** Rewrite in-repo .md links to on-site /docs routes; send src links to GitHub. */
export function rewriteDocLinks(content: string): string {
  const withMdLinks = content.replace(/\]\(([^)]+\.md)\)/g, (_match, href: string) => {
    const file = href.split("/").pop() ?? href;
    const slug = FILE_TO_SLUG[file];
    return slug ? `](/docs/${slug})` : `](${GITHUB_URL}/blob/master/docs/${file})`;
  });

  return withMdLinks.replace(
    /\]\(\.\.\/src\/([^)]+)\)/g,
    `](${GITHUB_URL}/blob/master/src/$1)`,
  );
}
