"use client";

import { useEffect, useState } from "react";

const achievements = [
  {
    quote:
      "Indexed MSMARCO-XI across Hindi, Bengali, Tamil, Telugu, Marathi, and English - one collection, six languages, comparable side by side.",
    detail: "Multilingual corpus",
    context: "ai4bharat / MSMARCO-XI",
    tag: "Six languages live",
  },
  {
    quote:
      "Every external dependency sits behind a port. Local ONNX and cloud Jina/Groq/Sarvam swap with FASTRAG_PROFILE - no rewrite of the pipeline.",
    detail: "Provider ports",
    context: "bootstrap.py wiring",
    tag: "Local ↔ cloud swap",
  },
  {
    quote:
      "Answers stream with citation markers that must resolve to retrieved chunks. Weak retrieval abstains; injection is refused before generate.",
    detail: "Groundedness",
    context: "CRAG + guardrails",
    tag: "Cite or stay silent",
  },
  {
    quote:
      "Voice is first-class: browser mic → 16 kHz WAV → Sarvam STT → the same SSE path as typed questions, with transcript in the decision trace.",
    detail: "Voice end-to-end",
    context: "/v1/voice/query/stream",
    tag: "Speak, then retrieve",
  },
];

const marqueeItems = [
  "MSMARCO-XI",
  "CRAG",
  "Hybrid RRF",
  "Sarvam STT",
  "Jina v3",
  "Qdrant",
  "Groq",
  "Neon",
  "Langfuse",
  "Six strategies",
];

export function TestimonialsSection() {
  const [activeIndex, setActiveIndex] = useState(0);
  const [isAnimating, setIsAnimating] = useState(false);

  useEffect(() => {
    const interval = setInterval(() => {
      setIsAnimating(true);
      setTimeout(() => {
        setActiveIndex((prev) => (prev + 1) % achievements.length);
        setIsAnimating(false);
      }, 300);
    }, 5000);
    return () => clearInterval(interval);
  }, []);

  const active = achievements[activeIndex];

  return (
    <section className="relative py-32 lg:py-40 border-t border-foreground/10 lg:pb-14">
      <div className="max-w-7xl mx-auto px-6 lg:px-12">
        <div className="flex items-center gap-4 mb-16">
          <span className="font-mono text-xs tracking-widest text-muted-foreground uppercase">
            What we achieved
          </span>
          <div className="flex-1 h-px bg-foreground/10" />
          <span className="font-mono text-xs text-muted-foreground">
            {String(activeIndex + 1).padStart(2, "0")} /{" "}
            {String(achievements.length).padStart(2, "0")}
          </span>
        </div>

        <div className="grid lg:grid-cols-12 gap-12 lg:gap-20">
          <div className="lg:col-span-8">
            <blockquote
              className={`transition-all duration-300 ${
                isAnimating ? "opacity-0 translate-y-4" : "opacity-100 translate-y-0"
              }`}
            >
              <p className="font-display text-4xl md:text-5xl lg:text-6xl leading-[1.1] tracking-tight text-foreground">
                &ldquo;{active.quote}&rdquo;
              </p>
            </blockquote>

            <div
              className={`mt-12 flex items-center gap-6 transition-all duration-300 delay-100 ${
                isAnimating ? "opacity-0" : "opacity-100"
              }`}
            >
              <div className="w-16 h-16 rounded-full bg-foreground/5 border border-foreground/10 flex items-center justify-center">
                <span className="font-mono text-sm text-foreground">
                  {String(activeIndex + 1).padStart(2, "0")}
                </span>
              </div>
              <div>
                <p className="text-lg font-medium text-foreground">{active.detail}</p>
                <p className="text-muted-foreground">{active.context}</p>
              </div>
            </div>
          </div>

          <div className="lg:col-span-4 flex flex-col justify-center">
            <div
              className={`p-8 border border-foreground/10 transition-all duration-300 ${
                isAnimating ? "opacity-0 scale-95" : "opacity-100 scale-100"
              }`}
            >
              <span className="font-mono text-xs tracking-widest text-muted-foreground uppercase block mb-4">
                Milestone
              </span>
              <p className="font-display text-3xl md:text-4xl text-foreground">{active.tag}</p>
            </div>

            <div className="flex gap-2 mt-8">
              {achievements.map((_, idx) => (
                <button
                  key={idx}
                  type="button"
                  aria-label={`Show achievement ${idx + 1}`}
                  onClick={() => {
                    setIsAnimating(true);
                    setTimeout(() => {
                      setActiveIndex(idx);
                      setIsAnimating(false);
                    }, 300);
                  }}
                  className={`h-2 transition-all duration-300 ${
                    idx === activeIndex
                      ? "w-8 bg-foreground"
                      : "w-2 bg-foreground/20 hover:bg-foreground/40"
                  }`}
                />
              ))}
            </div>
          </div>
        </div>

        <div className="mt-24 pt-12 border-t border-foreground/10">
          <p className="font-mono text-xs tracking-widest text-muted-foreground uppercase mb-8 text-center">
            Built on this stack
          </p>
        </div>
      </div>

      <div className="w-full overflow-hidden">
        <div className="flex w-max gap-16 items-center marquee">
          {[...Array(2)].map((_, setIdx) => (
            <div key={setIdx} className="flex gap-16 items-center shrink-0">
              {marqueeItems.map((item) => (
                <span
                  key={`${setIdx}-${item}`}
                  className="font-display text-xl md:text-2xl text-foreground/30 whitespace-nowrap hover:text-foreground transition-colors duration-300"
                >
                  {item}
                </span>
              ))}
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
