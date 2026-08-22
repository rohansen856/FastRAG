"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { ArrowUpRight } from "lucide-react";
import { DOC_SECTIONS } from "@/lib/docs";

export function DocsIndex() {
  const [visible, setVisible] = useState(false);
  const ref = useRef<HTMLElement>(null);

  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) setVisible(true);
      },
      { threshold: 0.08 },
    );
    if (ref.current) observer.observe(ref.current);
    return () => observer.disconnect();
  }, []);

  return (
    <section ref={ref}>
      <div
        className={`mb-10 transition-all duration-700 ${
          visible ? "opacity-100 translate-y-0" : "opacity-0 translate-y-6"
        }`}
      >
        <span className="inline-flex items-center gap-3 text-sm font-mono text-muted-foreground mb-4">
          <span className="w-8 h-px bg-foreground/30" />
          documentation
        </span>
        <h1 className="text-4xl lg:text-5xl font-display tracking-tight mb-4">Docs</h1>
        <p className="text-lg text-muted-foreground max-w-2xl leading-relaxed">
          Architecture, local setup, deployment, and pipeline deep-dives - rendered from the
          same markdown in the repo.
        </p>
      </div>

      <div className="space-y-12">
        {DOC_SECTIONS.map((section, sectionIndex) => (
          <div
            key={section.label}
            className={`transition-all duration-700 ${
              visible ? "opacity-100 translate-y-0" : "opacity-0 translate-y-6"
            }`}
            style={{ transitionDelay: `${sectionIndex * 80 + 120}ms` }}
          >
            <h2 className="text-xs font-mono uppercase tracking-widest text-muted-foreground mb-4">
              {section.label}
            </h2>
            <div className="grid gap-4 sm:grid-cols-2">
              {section.pages.map((page, pageIndex) => (
                <Link
                  key={page.slug}
                  href={`/docs/${page.slug}`}
                  className={`group block rounded-xl border border-foreground/10 bg-background/60 p-5 transition-all duration-300 hover:border-foreground/25 hover:bg-background hover:shadow-sm ${
                    visible ? "opacity-100 translate-y-0" : "opacity-0 translate-y-4"
                  }`}
                  style={{ transitionDelay: `${sectionIndex * 80 + pageIndex * 40 + 180}ms` }}
                >
                  <div className="flex items-start justify-between gap-3 mb-2">
                    <h3 className="font-medium text-foreground group-hover:underline underline-offset-4">
                      {page.title}
                    </h3>
                    <ArrowUpRight className="w-4 h-4 shrink-0 text-muted-foreground opacity-0 -translate-x-1 group-hover:opacity-100 group-hover:translate-x-0 transition-all" />
                  </div>
                  <p className="text-sm text-muted-foreground leading-relaxed">{page.description}</p>
                </Link>
              ))}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

interface DocsArticleProps {
  title: string;
  content: string;
}

export function DocsArticle({ title, content }: DocsArticleProps) {
  const [visible, setVisible] = useState(false);
  const ref = useRef<HTMLElement>(null);

  useEffect(() => {
    setVisible(false);
    const frame = requestAnimationFrame(() => setVisible(true));
    return () => cancelAnimationFrame(frame);
  }, [content]);

  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) setVisible(true);
      },
      { threshold: 0.05 },
    );
    if (ref.current) observer.observe(ref.current);
    return () => observer.disconnect();
  }, []);

  return (
    <article
      ref={ref}
      className={`min-w-0 transition-all duration-700 ${
        visible ? "opacity-100 translate-y-0" : "opacity-0 translate-y-6"
      }`}
    >
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          h1: ({ children }) => (
            <h1 className="text-3xl lg:text-4xl font-display tracking-tight mb-8 mt-2 first:mt-0">
              {children}
            </h1>
          ),
          h2: ({ children }) => (
            <h2 className="text-xl font-display tracking-tight mt-12 mb-4 pb-2 border-b border-foreground/10">
              {children}
            </h2>
          ),
          h3: ({ children }) => (
            <h3 className="text-lg font-medium mt-8 mb-3">{children}</h3>
          ),
          p: ({ children }) => (
            <p className="text-base text-foreground/85 leading-relaxed mb-4">{children}</p>
          ),
          ul: ({ children }) => (
            <ul className="list-disc pl-6 mb-4 space-y-2 text-foreground/85">{children}</ul>
          ),
          ol: ({ children }) => (
            <ol className="list-decimal pl-6 mb-4 space-y-2 text-foreground/85">{children}</ol>
          ),
          li: ({ children }) => <li className="leading-relaxed">{children}</li>,
          a: ({ href, children }) => (
            <a
              href={href}
              className="text-foreground underline underline-offset-4 decoration-foreground/30 hover:decoration-foreground"
              {...(href?.startsWith("http") ? { target: "_blank", rel: "noopener noreferrer" } : {})}
            >
              {children}
            </a>
          ),
          code: ({ className, children }) => {
            const isBlock = className?.includes("language-");
            if (isBlock) {
              return (
                <code className="block font-mono text-sm leading-relaxed text-foreground/90">
                  {children}
                </code>
              );
            }
            return (
              <code className="rounded bg-foreground/[0.06] px-1.5 py-0.5 font-mono text-[0.9em]">
                {children}
              </code>
            );
          },
          pre: ({ children }) => (
            <pre className="mb-6 overflow-x-auto rounded-xl border border-foreground/10 bg-foreground/[0.03] p-4">
              {children}
            </pre>
          ),
          table: ({ children }) => (
            <div className="mb-6 overflow-x-auto rounded-xl border border-foreground/10">
              <table className="w-full text-sm">{children}</table>
            </div>
          ),
          thead: ({ children }) => <thead className="border-b border-foreground/10 bg-foreground/[0.03]">{children}</thead>,
          th: ({ children }) => (
            <th className="px-4 py-3 text-left font-medium text-foreground">{children}</th>
          ),
          td: ({ children }) => (
            <td className="px-4 py-3 text-muted-foreground border-t border-foreground/5">{children}</td>
          ),
          blockquote: ({ children }) => (
            <blockquote className="mb-4 border-l-2 border-foreground/20 pl-4 text-muted-foreground italic">
              {children}
            </blockquote>
          ),
          hr: () => <hr className="my-10 border-foreground/10" />,
        }}
      >
        {content}
      </ReactMarkdown>
      <p className="sr-only">{title}</p>
    </article>
  );
}
