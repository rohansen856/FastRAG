"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { DOC_SECTIONS } from "@/lib/docs";

export function DocsSidebar() {
  const pathname = usePathname();

  return (
    <aside className="lg:sticky lg:top-28 lg:self-start">
      <nav className="space-y-8">
        <div>
          <Link
            href="/docs"
            className={`text-sm font-mono transition-colors ${
              pathname === "/docs"
                ? "text-foreground"
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            Overview
          </Link>
        </div>
        {DOC_SECTIONS.map((section) => (
          <div key={section.label}>
            <p className="mb-3 text-[10px] font-mono uppercase tracking-widest text-muted-foreground">
              {section.label}
            </p>
            <ul className="space-y-2">
              {section.pages.map((page) => {
                const href = `/docs/${page.slug}`;
                const active = pathname === href;
                return (
                  <li key={page.slug}>
                    <Link
                      href={href}
                      className={`block text-sm transition-colors duration-300 ${
                        active
                          ? "text-foreground font-medium"
                          : "text-muted-foreground hover:text-foreground"
                      }`}
                    >
                      {page.title}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
      </nav>
    </aside>
  );
}
