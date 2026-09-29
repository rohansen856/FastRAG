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
      {
        slug: "self-corpus",
        title: "The self-corpus",
        file: "self-corpus.md",
        description: "Indexing FastRAG's own code and docs, and deriving its golden set.",
      },
    ],
  },
  {
    label: "Diagrams",
    pages: [
      {
        slug: "diagrams",
        title: "Architecture diagrams",
        file: "diagrams/README.md",
        description: "Context, containers, sequences, data, deployment, lifecycles, network.",
      },
      {
        slug: "data-model-erd",
        title: "Data model (ERD)",
        file: "diagrams/05-data-model/erd.md",
        description: "Entities, attributes and cardinalities across Postgres, Qdrant and Redis.",
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

/** Resolve `href` against the folder of `file`, both relative to docs/ (e.g. "diagrams/x.md"). */
function resolveDocPath(file: string, href: string): string {
  const parts = file.split("/").slice(0, -1);
  for (const segment of href.split("/")) {
    if (segment === "..") parts.pop();
    else if (segment !== "." && segment !== "") parts.push(segment);
  }
  return parts.join("/");
}

/**
 * Rewrite in-repo links for the site: .md files to /docs routes (or GitHub when the file has
 * no page), rendered diagrams to their /diagrams copies, and src links to GitHub. Relative
 * links resolve from `file`, the markdown file's path under docs/.
 */
export function rewriteDocLinks(content: string, file: string): string {
  const withMdLinks = content.replace(/\]\(([^)]+\.md)\)/g, (_match, href: string) => {
    if (/^[a-z]+:\/\//i.test(href)) return `](${href})`;
    const path = resolveDocPath(file, href);
    const slug = FILE_TO_SLUG[path];
    return slug ? `](/docs/${slug})` : `](${GITHUB_URL}/blob/master/docs/${path})`;
  });

  const withDiagrams = withMdLinks.replace(/\]\(([^)]+\.html)\)/g, (_match, href: string) => {
    if (/^[a-z]+:\/\//i.test(href)) return `](${href})`;
    const path = resolveDocPath(file, href);
    return path.startsWith("diagrams/")
      ? `](/${path})`
      : `](${GITHUB_URL}/blob/master/docs/${path})`;
  });

  return withDiagrams.replace(
    /\]\(\.\.\/src\/([^)]+)\)/g,
    `](${GITHUB_URL}/blob/master/src/$1)`,
  );
}
