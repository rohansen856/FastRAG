"use client";

import { useState, useEffect, useRef } from "react";
import Image from "next/image";
import { ArrowUpRight, Github, Globe, Linkedin, Mail } from "lucide-react";
import { GITHUB_REPO_URL, type Developer } from "@/lib/site-config";

const highlights = [
  ...(GITHUB_REPO_URL
    ? [{ title: "Open source", description: "The whole pipeline lives in one public repo." }]
    : []),
  {
    title: "Cited or silent",
    description: "Every answer is grounded in sources, or the pipeline abstains.",
  },
  {
    title: "Local + cloud",
    description: "Same ports, free-tier providers when you need them.",
  },
  ...(GITHUB_REPO_URL
    ? [{ title: "Ship with us", description: "Issues and PRs welcome on GitHub." }]
    : []),
];

function initials(name: string): string {
  return name
    .split(/\s+/)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? "")
    .join("");
}

/** "github.com/rohansen856" from a profile URL, for the caption bar. */
function handle(url: string): string {
  return url.replace(/^https?:\/\/(www\.)?/, "").replace(/\/+$/, "");
}

function CornerTicks() {
  const tick = "pointer-events-none absolute h-3 w-3 border-foreground/40";
  return (
    <>
      <span aria-hidden className={`${tick} -left-px -top-px border-l border-t`} />
      <span aria-hidden className={`${tick} -right-px -top-px border-r border-t`} />
      <span aria-hidden className={`${tick} -bottom-px -left-px border-b border-l`} />
      <span aria-hidden className={`${tick} -bottom-px -right-px border-b border-r`} />
    </>
  );
}

export function DevelopersSection({ developer }: { developer: Developer }) {
  const [isVisible, setIsVisible] = useState(false);
  const sectionRef = useRef<HTMLElement>(null);

  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) setIsVisible(true);
      },
      { threshold: 0.1 },
    );

    if (sectionRef.current) observer.observe(sectionRef.current);
    return () => observer.disconnect();
  }, []);

  const links = [
    developer.github && { label: "GitHub", href: developer.github, icon: Github },
    developer.linkedin && { label: "LinkedIn", href: developer.linkedin, icon: Linkedin },
    developer.website && { label: "Website", href: developer.website, icon: Globe },
    developer.email && { label: developer.email, href: `mailto:${developer.email}`, icon: Mail },
  ].filter((link): link is { label: string; href: string; icon: typeof Github } => Boolean(link));
  const profile = developer.github ?? developer.linkedin ?? developer.website;

  return (
    <section id="developers" ref={sectionRef} className="relative py-24 lg:py-32 overflow-hidden">
      <div className="max-w-[1400px] mx-auto px-6 lg:px-12">
        <div className="grid lg:grid-cols-2 gap-16 lg:gap-24 items-start">
          <div
            className={`transition-all duration-700 ${
              isVisible ? "opacity-100 translate-y-0" : "opacity-0 translate-y-8"
            }`}
          >
            <span className="inline-flex items-center gap-3 text-sm font-mono text-muted-foreground mb-6">
              <span className="w-8 h-px bg-foreground/30" />
              the developer
            </span>
            <h2 className="text-4xl lg:text-6xl font-display tracking-tight mb-8">
              Built with love,
              <br />
              <span className="text-muted-foreground">for the community.</span>
            </h2>
            <p className="text-xl text-muted-foreground mb-12 leading-relaxed max-w-[52ch]">
              A voice-enabled, multilingual RAG stack you can run on free tiers, built and
              maintained by {developer.name}.{GITHUB_REPO_URL ? " Fork it without asking." : ""}
            </p>

            <div className="grid grid-cols-2 gap-6">
              {highlights.map((item, index) => (
                <div
                  key={item.title}
                  className={`transition-all duration-500 ${
                    isVisible ? "opacity-100 translate-y-0" : "opacity-0 translate-y-4"
                  }`}
                  style={{ transitionDelay: `${index * 50 + 200}ms` }}
                >
                  <h3 className="font-medium mb-1">{item.title}</h3>
                  <p className="text-sm text-muted-foreground">{item.description}</p>
                </div>
              ))}
            </div>
          </div>

          <div
            className={`lg:sticky lg:top-32 transition-all duration-700 delay-200 ${
              isVisible ? "opacity-100 translate-x-0" : "opacity-0 translate-x-8"
            }`}
          >
            <figure className="relative border border-foreground/10">
              <CornerTicks />
              <figcaption className="flex items-center justify-between gap-4 border-b border-foreground/10 px-6 py-3 font-mono text-[11px] uppercase tracking-widest text-muted-foreground">
                <span>{developer.role ?? "Developer"}</span>
                {profile && <span className="hidden truncate normal-case tracking-normal sm:inline">{handle(profile)}</span>}
              </figcaption>

              <div className="p-8 bg-foreground/[0.01]">
                <div className="flex flex-col sm:flex-row gap-8 items-start">
                  <div className="relative w-36 h-36 shrink-0 overflow-hidden border border-foreground/10 bg-foreground/5">
                    {developer.photo ? (
                      <Image
                        src={developer.photo}
                        alt={developer.name}
                        fill
                        className="object-cover border border-foreground/50 p-0.5"
                        sizes="144px"
                      />
                    ) : (
                      <span
                        aria-hidden
                        className="flex h-full w-full items-center justify-center font-display text-5xl tracking-tight text-foreground/70"
                      >
                        {initials(developer.name)}
                      </span>
                    )}
                  </div>
                  <div className="flex-1 min-w-0">
                    <h3 className="text-2xl font-display tracking-tight">{developer.name}</h3>
                    {developer.bio && (
                      <p className="mt-3 text-sm leading-relaxed text-muted-foreground">{developer.bio}</p>
                    )}
                    {links.length > 0 && (
                      <ul className="mt-6 flex flex-col gap-3">
                        {links.map(({ label, href, icon: Icon }) => (
                          <li key={href}>
                            <a
                              href={href}
                              {...(href.startsWith("http") ? { target: "_blank", rel: "noopener noreferrer" } : {})}
                              className="group inline-flex max-w-full items-center gap-3 text-sm text-muted-foreground underline decoration-foreground/25 underline-offset-4 hover:text-foreground hover:decoration-foreground"
                            >
                              <Icon className="w-4 h-4 shrink-0" />
                              <span className="truncate">{label}</span>
                              <ArrowUpRight className="h-3 w-3 shrink-0 opacity-0 transition-opacity group-hover:opacity-100" />
                            </a>
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                </div>
              </div>
            </figure>

            {GITHUB_REPO_URL && (
              <div className="mt-6 flex items-center gap-6 text-sm">
                <a
                  href={GITHUB_REPO_URL}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-foreground hover:underline underline-offset-4"
                >
                  View on GitHub
                </a>
              </div>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}
