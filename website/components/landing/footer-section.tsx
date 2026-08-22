"use client";

import Link from "next/link";
import { ArrowUpRight } from "lucide-react";
import { AnimatedWave } from "./animated-wave";

const GITHUB_URL = "https://github.com/rohansen856/FastRAG";

const footerLinks: Record<
  string,
  { name: string; href: string; badge?: string; external?: boolean }[]
> = {
  Product: [
    { name: "Features", href: "#features" },
    { name: "How it works", href: "#how-it-works" },
    { name: "Hosting", href: "#hosting" },
    { name: "Providers", href: "#integrations" },
  ],
  Pipeline: [
    { name: "Guardrails", href: "/docs/guardrails" },
    { name: "Benchmarks", href: "/docs/benchmarking" },
    { name: "Latency", href: "/docs/latency" },
    { name: "The team", href: "/developers" },
  ],
  Source: [
    { name: "Repository", href: GITHUB_URL, external: true },
    { name: "Docs", href: "/docs" },
    {
      name: "Running locally",
      href: "/docs/running-locally",
    },
    {
      name: "Providers",
      href: "/docs/providers",
    },
    {
      name: "Architecture",
      href: "/docs/architecture",
    },
  ],
  Team: [
    { name: "Rohan Sen", href: "https://github.com/rohansen856", external: true },
    { name: "Vansh Gularia", href: "https://github.com/vanshg101", external: true },
    { name: "Nitin Pandey", href: "https://github.com/Nitin192005", external: true },
  ],
};

const socialLinks = [
  { name: "GitHub", href: GITHUB_URL },
  { name: "Rohan", href: "https://www.linkedin.com/in/rohansen856" },
  { name: "Vansh", href: "https://www.linkedin.com/in/vansh-gularia-bb6078243/" },
  { name: "Nitin", href: "https://www.linkedin.com/in/nitin-pandey-dev" },
];

export function FooterSection() {
  return (
    <footer className="relative border-t border-foreground/10">
      <div className="absolute inset-0 h-64 opacity-20 pointer-events-none overflow-hidden">
        <AnimatedWave />
      </div>

      <div className="relative z-10 max-w-[1400px] mx-auto px-6 lg:px-12">
        <div className="py-16 lg:py-24">
          <div className="grid grid-cols-2 md:grid-cols-6 gap-12 lg:gap-8">
            <div className="col-span-2">
              <Link href="/" className="inline-flex items-center gap-2 mb-6">
                <img src="/logo.svg" alt="" width={28} height={28} className="h-7 w-7" />
                <span className="text-2xl font-display">FastRAG</span>
                <span className="text-xs text-muted-foreground font-mono">OSS</span>
              </Link>

              <p className="text-muted-foreground leading-relaxed mb-8 max-w-xs">
                Voice-enabled, multilingual RAG. Answers only from retrieved sources - or it
                stays silent.
              </p>

              <div className="flex flex-wrap gap-x-6 gap-y-3">
                {socialLinks.map((link) => (
                  <a
                    key={link.name}
                    href={link.href}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-sm text-muted-foreground hover:text-foreground transition-colors flex items-center gap-1 group"
                  >
                    {link.name}
                    <ArrowUpRight className="w-3 h-3 opacity-0 -translate-x-1 group-hover:opacity-100 group-hover:translate-x-0 transition-all" />
                  </a>
                ))}
              </div>
            </div>

            {Object.entries(footerLinks).map(([title, links]) => (
              <div key={title}>
                <h3 className="text-sm font-medium mb-6">{title}</h3>
                <ul className="space-y-4">
                  {links.map((link) => (
                    <li key={link.name}>
                      <a
                        href={link.href}
                        {...(link.external
                          ? { target: "_blank", rel: "noopener noreferrer" }
                          : {})}
                        className="text-sm text-muted-foreground hover:text-foreground transition-colors inline-flex items-center gap-2"
                      >
                        {link.name}
                        {link.badge && (
                          <span className="text-xs px-2 py-0.5 bg-foreground text-background rounded-full">
                            {link.badge}
                          </span>
                        )}
                      </a>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </div>

        <div className="py-8 border-t border-foreground/10 flex flex-col md:flex-row items-center justify-between gap-4">
          <p className="text-sm text-muted-foreground">
            2026 FastRAG. Open source.
          </p>

          <a
            href={GITHUB_URL}
            target="_blank"
            rel="noopener noreferrer"
            className="text-sm text-muted-foreground hover:text-foreground transition-colors font-mono"
          >
            github.com/rohansen856/FastRAG
          </a>
        </div>
      </div>
    </footer>
  );
}
