import { notFound } from "next/navigation";
import { DocsShell } from "@/components/docs/docs-shell";
import { DocsArticle } from "@/components/docs/docs-content";
import {
  ALL_DOC_PAGES,
  getDocBySlug,
  rewriteDocLinks,
} from "@/lib/docs";
import { loadDocMarkdown } from "@/lib/docs-server";

export function generateStaticParams() {
  return ALL_DOC_PAGES.map((page) => ({ slug: page.slug }));
}

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const doc = getDocBySlug(slug);
  if (!doc) return { title: "Docs · FastRAG" };
  return {
    title: `${doc.title} · FastRAG Docs`,
    description: doc.description,
  };
}

export default async function DocSlugPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const doc = getDocBySlug(slug);
  if (!doc) notFound();

  const raw = loadDocMarkdown(doc.file);
  const content = rewriteDocLinks(raw.replace(/^#\s+.+\n+/, ""));

  return (
    <DocsShell>
      <DocsArticle title={doc.title} content={content} />
    </DocsShell>
  );
}
