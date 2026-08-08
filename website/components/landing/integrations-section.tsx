"use client";

import { useEffect, useState, useRef } from "react";

/** Third-party services FastRAG actually wires in bootstrap (local + cloud). */
const services = [
  { name: "PostgreSQL", category: "Registry · Neon / Compose" },
  { name: "Qdrant", category: "Vector store" },
  { name: "Jina", category: "Embeddings + rerank" },
  { name: "Groq", category: "LLM generation" },
  { name: "Sarvam", category: "Speech-to-text" },
  { name: "Redis", category: "Exact + semantic cache" },
  { name: "Langfuse", category: "Tracing" },
  { name: "Ollama", category: "Local LLM" },
  { name: "FastEmbed", category: "Local ONNX embed / rerank" },
  { name: "OpenRouter", category: "LLM fallback" },
  { name: "Neon", category: "Hosted Postgres" },
  { name: "Render", category: "API hosting" },
  { name: "Vercel", category: "Web hosting" },
  { name: "ElevenLabs", category: "Optional STT" },
];

function ServiceCard({ name, category }: { name: string; category: string }) {
  return (
    <div className="shrink-0 px-8 py-6 border border-foreground/10 hover:border-foreground/30 hover:bg-foreground/[0.02] transition-all duration-300 group">
      <div className="text-lg font-medium group-hover:translate-x-1 transition-transform">{name}</div>
      <div className="text-sm text-muted-foreground">{category}</div>
    </div>
  );
}

export function IntegrationsSection() {
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

  return (
    <section id="integrations" ref={sectionRef} className="relative py-24 lg:py-32 overflow-hidden">
      <div className="max-w-[1400px] mx-auto px-6 lg:px-12">
        <div
          className={`text-center max-w-3xl mx-auto mb-16 lg:mb-24 transition-all duration-700 ${
            isVisible ? "opacity-100 translate-y-0" : "opacity-0 translate-y-8"
          }`}
        >
          <span className="inline-flex items-center gap-3 text-sm font-mono text-muted-foreground mb-6">
            <span className="w-8 h-px bg-foreground/30" />
            Providers
            <span className="w-8 h-px bg-foreground/30" />
          </span>
          <h2 className="text-4xl lg:text-6xl font-display tracking-tight mb-6">
            Swappable free-tier
            <br />
            stack.
          </h2>
          <p className="text-xl text-muted-foreground">
            Every dependency sits behind a port. Local uses ONNX + Compose; cloud swaps in Jina,
            Groq, Sarvam, Qdrant Cloud, Neon, and Redis Cloud without rewriting the pipeline.
          </p>
        </div>
      </div>

      <div className="w-full mb-6 overflow-hidden">
        <div className="flex w-max gap-6 marquee">
          {[...Array(2)].map((_, setIndex) => (
            <div key={setIndex} className="flex shrink-0 gap-6">
              {services.map((service) => (
                <ServiceCard key={`${service.name}-${setIndex}`} {...service} />
              ))}
            </div>
          ))}
        </div>
      </div>

      <div className="w-full overflow-hidden">
        <div className="flex w-max gap-6 marquee-reverse">
          {[...Array(2)].map((_, setIndex) => (
            <div key={setIndex} className="flex shrink-0 gap-6">
              {[...services].reverse().map((service) => (
                <ServiceCard key={`${service.name}-reverse-${setIndex}`} {...service} />
              ))}
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
