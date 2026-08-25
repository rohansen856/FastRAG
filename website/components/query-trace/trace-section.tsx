"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";

export function TraceSection({
  children,
  className = "",
  delay = 0,
}: {
  children: ReactNode;
  className?: string;
  delay?: number;
}) {
  const ref = useRef<HTMLElement>(null);
  const [visible, setVisible] = useState(false);

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
    <section
      ref={ref}
      className={`h-fit self-start rounded-xl border border-foreground/10 bg-background/70 p-5 lg:p-6 shadow-sm transition-all duration-700 ${className} ${
        visible ? "opacity-100 translate-y-0" : "opacity-0 translate-y-6"
      }`}
      style={{ transitionDelay: `${delay}ms` }}
    >
      {children}
    </section>
  );
}

export function TraceSectionTitle({ children }: { children: ReactNode }) {
  return (
    <h2 className="mb-4 text-xs font-mono uppercase tracking-widest text-muted-foreground">
      {children}
    </h2>
  );
}
