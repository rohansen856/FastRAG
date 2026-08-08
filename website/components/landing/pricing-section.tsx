"use client";

import { ArrowRight, Check } from "lucide-react";

const profiles = [
  {
    name: "Local",
    description: "Compose + ONNX on your machine - the sub-200ms retrieval rig",
    badge: null,
    headline: "In-process",
    subhead: "No cloud hops on retrieve",
    features: [
      "FASTRAG_PROFILE=local",
      "Embeddings: BAAI/bge-base-en-v1.5 (ONNX)",
      "Rerank: Xenova/ms-marco-MiniLM-L-6-v2",
      "Qdrant + Postgres + Redis via Compose",
      "LLM: Ollama (OpenAI-compatible)",
      "Semantic cache off (plain Redis)",
      "STT: Sarvam key optional (text-only without it)",
      "Benchmark target: <200ms retrieval P95",
    ],
    cta: "See local setup",
    href: "https://github.com/rohansen856/FastRAG/blob/master/docs/local-setup.md",
    popular: false,
  },
  {
    name: "Hosted cloud",
    description: "What we run on free tiers today - multilingual demo",
    badge: "Current",
    headline: "Free tiers",
    subhead: "Render + Vercel ready",
    features: [
      "FASTRAG_PROFILE=cloud",
      "Embeddings + rerank: Jina (v3 / v2-multilingual)",
      "Vectors: Qdrant Cloud (1 GB free)",
      "Registry: Neon Postgres",
      "Cache: Redis Cloud (+ RediSearch)",
      "LLM: Groq free · OpenRouter fallback",
      "STT: Sarvam Saaras v3",
      "Tracing: Langfuse Cloud",
      "Sparse retrieval off (512 MB RAM)",
    ],
    cta: "See cloud env",
    href: "https://github.com/rohansen856/FastRAG/blob/master/.env.cloud.example",
    popular: true,
  },
  {
    name: "Best results",
    description: "Config that maximizes quality when quota and RAM allow",
    badge: null,
    headline: "Quality first",
    subhead: "Same ports, fuller stack",
    features: [
      "Jina (or multilingual local) for Indic queries",
      "Index all six chunking strategies",
      "CRAG on · calibrated thresholds",
      "Semantic cache on (Redis Stack / Cloud)",
      "Hybrid dense + sparse when RAM allows",
      "Stronger Groq / paid LLM + fallback",
      "Full MSMARCO-XI ingest (not a tiny subset)",
      "Golden gate + bench-latency both profiles",
    ],
    cta: "Read providers",
    href: "https://github.com/rohansen856/FastRAG/blob/master/docs/providers.md",
    popular: false,
  },
];

export function PricingSection() {
  return (
    <section id="hosting" className="relative py-32 lg:py-40 border-t border-foreground/10">
      <div className="max-w-7xl mx-auto px-6 lg:px-12">
        <div className="max-w-3xl mb-20">
          <span className="font-mono text-xs tracking-widest text-muted-foreground uppercase block mb-6">
            Hosting
          </span>
          <h2 className="font-display text-5xl md:text-6xl lg:text-7xl tracking-tight text-foreground mb-6">
            Three ways to
            <br />
            <span className="text-stroke">run it</span>
          </h2>
          <p className="text-lg text-muted-foreground max-w-xl">
            Local for the latency claim, free cloud for the live multilingual demo, and a quality
            profile when you can spend more tokens and disk.
          </p>
        </div>

        <div className="grid md:grid-cols-3 gap-px bg-foreground/10">
          {profiles.map((plan, idx) => (
            <div
              key={plan.name}
              className={`relative p-8 lg:p-12 bg-background ${
                plan.popular ? "md:-my-4 md:py-12 lg:py-16 border-2 border-foreground" : ""
              }`}
            >
              {plan.badge && (
                <span className="absolute -top-3 left-8 px-3 py-1 bg-foreground text-primary-foreground text-xs font-mono uppercase tracking-widest">
                  {plan.badge}
                </span>
              )}

              <div className="mb-8">
                <span className="font-mono text-xs text-muted-foreground">
                  {String(idx + 1).padStart(2, "0")}
                </span>
                <h3 className="font-display text-3xl text-foreground mt-2">{plan.name}</h3>
                <p className="text-sm text-muted-foreground mt-2">{plan.description}</p>
              </div>

              <div className="mb-8 pb-8 border-b border-foreground/10">
                <span className="font-display text-4xl lg:text-5xl text-foreground block">
                  {plan.headline}
                </span>
                <span className="text-sm text-muted-foreground mt-2 block">{plan.subhead}</span>
              </div>

              <ul className="space-y-4 mb-10">
                {plan.features.map((feature) => (
                  <li key={feature} className="flex items-start gap-3">
                    <Check className="w-4 h-4 text-foreground mt-0.5 shrink-0" />
                    <span className="text-sm text-muted-foreground">{feature}</span>
                  </li>
                ))}
              </ul>

              <a
                href={plan.href}
                target="_blank"
                rel="noopener noreferrer"
                className={`w-full py-4 flex items-center justify-center gap-2 text-sm font-medium transition-all group ${
                  plan.popular
                    ? "bg-foreground text-primary-foreground hover:bg-foreground/90"
                    : "border border-foreground/20 text-foreground hover:border-foreground hover:bg-foreground/5"
                }`}
              >
                {plan.cta}
                <ArrowRight className="w-4 h-4 transition-transform group-hover:translate-x-1" />
              </a>
            </div>
          ))}
        </div>

        <p className="mt-12 text-center text-sm text-muted-foreground">
          Cloud hops will not meet the local 200ms retrieval target - that number is measured on
          the local profile only.{" "}
          <a
            href="https://github.com/rohansen856/FastRAG/blob/master/docs/latency.md"
            target="_blank"
            rel="noopener noreferrer"
            className="underline underline-offset-4 hover:text-foreground transition-colors"
          >
            Read latency.md
          </a>
        </p>
      </div>
    </section>
  );
}
