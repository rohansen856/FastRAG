"use client";

import { useEffect, useState, useRef } from "react";

/** Local-profile stage budget: the six legs that make up the sub-200ms claim. */
const stages = [
  { name: "Guardrails", detail: "Off-topic · injection · language", latency: "~2ms" },
  { name: "Embedding", detail: "ONNX dense query vector", latency: "~18ms" },
  { name: "Cache", detail: "Exact + optional semantic", latency: "~3ms" },
  { name: "Retrieval", detail: "Hybrid dense + sparse", latency: "~25ms" },
  { name: "Rerank", detail: "Cross-encoder top-k", latency: "~90ms" },
  { name: "CRAG", detail: "Correct · strip · rewrite", latency: "~5ms" },
];

export function InfrastructureSection() {
  const [isVisible, setIsVisible] = useState(false);
  const [activeStage, setActiveStage] = useState(0);
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

  useEffect(() => {
    const interval = setInterval(() => {
      setActiveStage((prev) => (prev + 1) % stages.length);
    }, 2000);
    return () => clearInterval(interval);
  }, []);

  return (
    <section ref={sectionRef} className="relative py-24 lg:py-32 overflow-hidden">
      <div className="max-w-[1400px] mx-auto px-6 lg:px-12">
        <div className="grid lg:grid-cols-2 gap-16 lg:gap-24 items-center">
          <div
            className={`transition-all duration-700 ${
              isVisible ? "opacity-100 translate-x-0" : "opacity-0 -translate-x-8"
            }`}
          >
            <span className="inline-flex items-center gap-3 text-sm font-mono text-muted-foreground mb-6">
              <span className="w-8 h-px bg-foreground/30" />
              Latency
            </span>
            <h2 className="text-4xl lg:text-6xl font-display tracking-tight mb-8">
              Sub-200ms
              <br />
              retrieval.
            </h2>
            <p className="text-xl text-muted-foreground leading-relaxed mb-12">
              Guardrails through CRAG are measured as one pipeline. The local profile keeps that
              under 200ms. Speech-to-text and generation are timed separately so a slow model
              never hides a retrieval regression.
            </p>

            <div className="grid grid-cols-3 gap-8">
              <div>
                <div className="text-4xl lg:text-5xl font-display mb-2">6</div>
                <div className="text-sm text-muted-foreground">Languages indexed</div>
              </div>
              <div>
                <div className="text-4xl lg:text-5xl font-display mb-2">2</div>
                <div className="text-sm text-muted-foreground">Profiles · local / cloud</div>
              </div>
              <div>
                <div className="text-4xl lg:text-5xl font-display mb-2">&lt;200ms</div>
                <div className="text-sm text-muted-foreground">Retrieval P95 target</div>
              </div>
            </div>
          </div>

          <div
            className={`transition-all duration-700 delay-200 ${
              isVisible ? "opacity-100 translate-x-0" : "opacity-0 translate-x-8"
            }`}
          >
            <div className="border border-foreground/10">
              <div className="px-6 py-4 border-b border-foreground/10 flex items-center justify-between">
                <span className="text-sm font-mono text-muted-foreground">Retrieval pipeline</span>
                <span className="flex items-center gap-2 text-xs font-mono text-green-600">
                  <span className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
                  Local profile
                </span>
              </div>

              <div>
                {stages.map((stage, index) => (
                  <div
                    key={stage.name}
                    className={`px-6 py-5 border-b border-foreground/5 last:border-b-0 flex items-center justify-between transition-all duration-300 ${
                      activeStage === index ? "bg-foreground/[0.02]" : ""
                    }`}
                  >
                    <div className="flex items-center gap-4">
                      <span
                        className={`w-2 h-2 rounded-full transition-colors duration-300 ${
                          activeStage === index ? "bg-foreground" : "bg-foreground/20"
                        }`}
                      />
                      <div>
                        <div className="font-medium">{stage.name}</div>
                        <div className="text-sm text-muted-foreground">{stage.detail}</div>
                      </div>
                    </div>
                    <span className="font-mono text-sm text-muted-foreground">{stage.latency}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
