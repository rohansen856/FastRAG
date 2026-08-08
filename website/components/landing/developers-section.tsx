"use client";

import { useState, useEffect, useRef } from "react";
import Image from "next/image";
import { Github, Linkedin } from "lucide-react";

const developers = [
  {
    id: "rohan",
    name: "Rohan Sen",
    short: "Rohan",
    role: "Builder",
    photo: "/developers/rohan.png",
    github: "https://github.com/rohansen856",
    linkedin: "https://www.linkedin.com/in/rohansen856",
  },
  {
    id: "vansh",
    name: "Vansh Gularia",
    short: "Vansh",
    role: "Builder",
    photo: "/developers/vansh.png",
    github: "https://github.com/vanshg101",
    linkedin: "https://www.linkedin.com/in/vansh-gularia-bb6078243/",
  },
  {
    id: "nitin",
    name: "Nitin Pandey",
    short: "Nitin",
    role: "Builder",
    photo: "/developers/nitin.png",
    github: "https://github.com/Nitin192005",
    linkedin: "https://www.linkedin.com/in/nitin-pandey-dev",
  },
];

const highlights = [
  {
    title: "Open source",
    description: "The whole pipeline lives in one public repo.",
  },
  {
    title: "Cited or silent",
    description: "Every answer is grounded in sources, or the pipeline abstains.",
  },
  {
    title: "Local + cloud",
    description: "Same ports, free-tier providers when you need them.",
  },
  {
    title: "Ship with us",
    description: "Issues and PRs welcome on GitHub.",
  },
];

export function DevelopersSection() {
  const [activeTab, setActiveTab] = useState(0);
  const [isVisible, setIsVisible] = useState(false);
  const sectionRef = useRef<HTMLElement>(null);
  const person = developers[activeTab];

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
              the developers
            </span>
            <h2 className="text-4xl lg:text-6xl font-display tracking-tight mb-8">
              Built with love,
              <br />
              <span className="text-muted-foreground">for the community.</span>
            </h2>
            <p className="text-xl text-muted-foreground mb-12 leading-relaxed">
              Three people shipping a voice-enabled, multilingual RAG stack you can run on free
              tiers - and fork without asking.
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
            <div className="border border-foreground/10 overflow-hidden">
              <div className="flex items-center border-b border-foreground/10">
                {developers.map((dev, idx) => (
                  <button
                    key={dev.id}
                    type="button"
                    onClick={() => setActiveTab(idx)}
                    className={`px-6 py-4 text-sm font-mono capitalize transition-colors relative ${
                      activeTab === idx
                        ? "text-foreground"
                        : "text-muted-foreground hover:text-foreground"
                    }`}
                  >
                    {dev.short}
                    {activeTab === idx && (
                      <span className="absolute bottom-0 left-0 right-0 h-px bg-foreground" />
                    )}
                  </button>
                ))}
              </div>

              <div className="p-8 bg-foreground/[0.01]">
                <div key={person.id} className="flex flex-col sm:flex-row gap-8 items-start">
                  <div className="relative w-36 h-36 shrink-0 overflow-hidden border border-foreground/10 bg-foreground/5">
                    <Image
                      src={person.photo}
                      alt={person.name}
                      fill
                      className="object-cover border border-foreground/50 p-0.5"
                      sizes="144px"
                    />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-xs font-mono text-muted-foreground mb-2 uppercase tracking-wide">
                      {person.role}
                    </p>
                    <h3 className="text-2xl font-display tracking-tight mb-6">{person.name}</h3>
                    <div className="flex flex-col gap-3">
                      <a
                        href={person.github}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-3 text-sm text-muted-foreground hover:text-foreground underline"
                      >
                        <Github className="w-4 h-4 shrink-0" />
                        GitHub
                      </a>
                      <a
                        href={person.linkedin}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-3 text-sm text-muted-foreground hover:text-foreground underline"
                      >
                        <Linkedin className="w-4 h-4 shrink-0" />
                        LinkedIn
                      </a>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <div className="mt-6 flex items-center gap-6 text-sm">
              <a
                href="https://github.com/rohansen856/FastRAG"
                target="_blank"
                rel="noopener noreferrer"
                className="text-foreground hover:underline underline-offset-4"
              >
                View on GitHub
              </a>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
