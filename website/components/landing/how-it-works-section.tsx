"use client";

import { useEffect, useRef, useState } from "react";

const steps = [
  {
    number: "I",
    title: "Hear the question",
    description:
      "Type it, or speak it. Voice becomes 16 kHz mono WAV, Sarvam transcribes, and guardrails check language, injection, and off-topic before anything is retrieved.",
    code: `POST /v1/voice/query/stream
# multipart: question.wav

# or text
POST /v1/query/stream
{ "query": "…", "strategy": "sentence" }

# guardrails first → allow | refuse`,
    file: "ingress.py",
  },
  {
    number: "II",
    title: "Retrieve and grade",
    description:
      "Embed the query, hit exact/semantic cache, hybrid-search Qdrant, rerank, then CRAG: correct → keep, ambiguous → strip, incorrect → one rewrite or abstain.",
    code: `embed(query)
cache.lookup()          # exact · semantic
hybrid_retrieve(k)      # dense + sparse
rerank(candidates)
crag.grade(top_score)
  # correct | strip | rewrite | abstain`,
    file: "pipeline.py",
  },
  {
    number: "III",
    title: "Answer or stay silent",
    description:
      "The generator streams only from supplied chunks. Every sentence needs a valid citation. No match, no answer - outcome answered, no_answer, or refused.",
    code: `for sentence in generate(context):
  if not cite(sentence, chunks):
    reject(sentence)

# SSE: transcript → answer_chunk → final
# outcome: answered | no_answer | refused`,
    file: "generate.py",
  },
];

export function HowItWorksSection() {
  const [activeStep, setActiveStep] = useState(0);
  const [isVisible, setIsVisible] = useState(false);
  const sectionRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) setIsVisible(true);
      },
      { threshold: 0.1 }
    );

    if (sectionRef.current) observer.observe(sectionRef.current);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    const interval = setInterval(() => {
      setActiveStep((prev) => (prev + 1) % steps.length);
    }, 5000);
    return () => clearInterval(interval);
  }, []);

  return (
    <section
      id="how-it-works"
      ref={sectionRef}
      className="relative py-24 lg:py-32 bg-foreground text-background overflow-hidden"
    >
      {/* Diagonal lines pattern */}
      <div className="absolute inset-0 opacity-[0.03] pointer-events-none">
        <div className="absolute inset-0" style={{
          backgroundImage: `repeating-linear-gradient(
            -45deg,
            transparent,
            transparent 40px,
            currentColor 40px,
            currentColor 41px
          )`
        }} />
      </div>

      <div className="relative z-10 max-w-[1400px] mx-auto px-6 lg:px-12 min-w-0">
        {/* Header */}
        <div className="mb-16 lg:mb-24">
          <span className="inline-flex items-center gap-3 text-sm font-mono text-background/50 mb-6">
            <span className="w-8 h-px bg-background/30" />
            Process
          </span>
          <h2
            className={`text-4xl lg:text-6xl font-display tracking-tight transition-all duration-700 ${
              isVisible ? "opacity-100 translate-y-0" : "opacity-0 translate-y-4"
            }`}
          >
            Three steps.
            <br />
            <span className="text-background/50">One grounded pipeline.</span>
          </h2>
        </div>

        {/* Main content - min-w-0 so the code pane cannot stretch the grid */}
        <div className="grid lg:grid-cols-2 gap-10 lg:gap-24 min-w-0">
          {/* Steps */}
          <div className="space-y-0 min-w-0">
            {steps.map((step, index) => (
              <button
                key={step.number}
                type="button"
                onClick={() => setActiveStep(index)}
                className={`w-full max-w-full min-w-0 text-left py-8 border-b border-background/10 transition-all duration-500 group whitespace-normal ${
                  activeStep === index ? "opacity-100" : "opacity-40 hover:opacity-70"
                }`}
              >
                <div className="flex items-start gap-4 sm:gap-6 min-w-0">
                  <span className="font-display text-3xl text-background/30 shrink-0">{step.number}</span>
                  <div className="min-w-0 flex-1">
                    <h3 className="text-2xl lg:text-3xl font-display mb-3 break-words group-hover:translate-x-2 transition-transform duration-300">
                      {step.title}
                    </h3>
                    <p className="text-background/60 leading-relaxed wrap-break-word">
                      {step.description}
                    </p>
                    
                    {/* Progress indicator */}
                    {activeStep === index && (
                      <div className="mt-4 h-px bg-background/20 overflow-hidden">
                        <div 
                          className="h-full bg-background w-0"
                          style={{
                            animation: 'progress 5s linear forwards'
                          }}
                        />
                      </div>
                    )}
                  </div>
                </div>
              </button>
            ))}
          </div>

          {/* Code display */}
          <div className="lg:sticky lg:top-32 self-start min-w-0 w-full">
            <div className="border border-background/10 overflow-hidden max-w-full">
              {/* Window header */}
              <div className="px-4 sm:px-6 py-4 border-b border-background/10 flex items-center justify-between gap-3">
                <div className="flex gap-2 shrink-0">
                  <div className="w-3 h-3 rounded-full bg-background/20" />
                  <div className="w-3 h-3 rounded-full bg-background/20" />
                  <div className="w-3 h-3 rounded-full bg-background/20" />
                </div>
                <span className="text-xs font-mono text-background/40 truncate">{steps[activeStep].file}</span>
              </div>

              {/* Code content */}
              <div className="p-4 sm:p-8 font-mono text-sm min-h-[280px] overflow-x-auto">
                <pre className="text-background/70 whitespace-pre-wrap break-all">
                  {steps[activeStep].code.split('\n').map((line, lineIndex) => (
                    <div 
                      key={`${activeStep}-${lineIndex}`} 
                      className="leading-loose code-line-reveal"
                      style={{ 
                        animationDelay: `${lineIndex * 80}ms`,
                      }}
                    >
                      <span className="text-background/20 select-none inline-block w-6 sm:w-8 shrink-0">
                        {lineIndex + 1}
                      </span>
                      {line || " "}
                    </div>
                  ))}
                </pre>
              </div>

              {/* Status */}
              <div className="px-6 py-4 border-t border-background/10 flex items-center gap-3">
                <span className="w-2 h-2 rounded-full bg-green-400 animate-pulse" />
                <span className="text-xs font-mono text-background/40">Ready</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <style jsx>{`
        @keyframes progress {
          from { width: 0%; }
          to { width: 100%; }
        }
        
        .code-line-reveal {
          opacity: 0;
          transform: translateX(-8px);
          animation: lineReveal 0.4s cubic-bezier(0.22, 1, 0.36, 1) forwards;
        }
        
        @keyframes lineReveal {
          to {
            opacity: 1;
            transform: translateX(0);
          }
        }
      `}</style>
    </section>
  );
}
