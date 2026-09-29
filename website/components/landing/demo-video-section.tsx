"use client";

import { useEffect, useRef, useState } from "react";
import { Play } from "lucide-react";

const YOUTUBE_ID = "7SnSBCGezbU";
const EMBED_ORIGIN = "https://www.youtube-nocookie.com";

/**
 * Where the display sits inside public/demo/macbook-pro-16.webp, in percent of the image. The
 * image is the Figma "MacBook Pro 16" mockup flattened onto white; it is drawn with
 * mix-blend-multiply so its white areas take the section background. The display is enlarged
 * by a hair on every side so no seam shows against the black bezel.
 */
const SCREEN = { left: 10.6, top: 1.5, width: 78.8, height: 62.5 };
/** The camera notch, in percent of the display. */
const NOTCH = { width: 10.95, height: 2.85 };

/** Opens the connections the player needs, so the click-to-play wait is shorter. */
function warmConnections() {
  for (const href of [EMBED_ORIGIN, "https://www.google.com"]) {
    if (document.head.querySelector(`link[rel="preconnect"][href="${href}"]`)) continue;
    const link = document.createElement("link");
    link.rel = "preconnect";
    link.href = href;
    link.crossOrigin = "";
    document.head.append(link);
  }
}

/**
 * The launch video inside a MacBook mockup. Nothing from YouTube loads with the page: the
 * screen shows a self-hosted poster frame, and the player iframe is only created when the
 * visitor presses play. Hovering or focusing the button warms the connection first.
 */
export function DemoVideoSection() {
  const [isVisible, setIsVisible] = useState(false);
  const [playing, setPlaying] = useState(false);
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
    <section id="demo" ref={sectionRef} className="relative py-24 lg:py-32">
      <div className="max-w-[1400px] mx-auto px-6 lg:px-12">
        <div className="mb-12 lg:mb-16">
          <span className="inline-flex items-center gap-3 text-sm font-mono text-muted-foreground mb-6">
            <span className="w-8 h-px bg-foreground/30" />
            Demo
          </span>
          <h2
            className={`text-4xl lg:text-6xl font-display tracking-tight transition-all duration-700 ${
              isVisible ? "opacity-100 translate-y-0" : "opacity-0 translate-y-4"
            }`}
          >
            Thirty seconds,
            <br />
            <span className="text-muted-foreground">question to citation.</span>
          </h2>
        </div>

        <div
          className={`mx-auto max-w-5xl transition-all duration-1000 delay-150 ${
            isVisible ? "opacity-100 translate-y-0" : "opacity-0 translate-y-12"
          }`}
        >
          {/* The stage paints the page background itself: the reveal transition makes this a
              stacking context, and multiply needs an opaque backdrop inside it. */}
          <div className="relative aspect-[2000/1633] bg-background">
            <img
              src="/demo/macbook-pro-16.webp"
              alt=""
              width={2000}
              height={1633}
              loading="lazy"
              decoding="async"
              className="absolute inset-0 h-full w-full mix-blend-multiply select-none"
              draggable={false}
            />

            <div
              className="absolute overflow-hidden rounded-t-[1%] bg-black"
              style={{
                left: `${SCREEN.left}%`,
                top: `${SCREEN.top}%`,
                width: `${SCREEN.width}%`,
                height: `${SCREEN.height}%`,
              }}
            >
              {playing ? (
                <iframe
                  src={`${EMBED_ORIGIN}/embed/${YOUTUBE_ID}?autoplay=1&rel=0&playsinline=1`}
                  title="FastRAG demo video"
                  allow="autoplay; encrypted-media; picture-in-picture; fullscreen"
                  allowFullScreen
                  referrerPolicy="strict-origin-when-cross-origin"
                  className="absolute inset-0 h-full w-full border-0"
                />
              ) : (
                <button
                  type="button"
                  onClick={() => setPlaying(true)}
                  onPointerEnter={warmConnections}
                  onFocus={warmConnections}
                  aria-label="Play the FastRAG demo video"
                  className="group absolute inset-0 flex items-center justify-center"
                >
                  <img
                    src="/demo/fastrag-demo-poster.webp"
                    alt=""
                    width={1600}
                    height={900}
                    loading="lazy"
                    decoding="async"
                    className="absolute inset-0 h-full w-full object-contain transition-opacity duration-300 group-hover:opacity-80"
                  />
                  <span className="relative flex items-center gap-3 rounded-full bg-white/95 py-2.5 pl-3 pr-5 text-sm font-medium text-black shadow-lg ring-1 ring-black/5 transition-transform duration-300 group-hover:scale-105 group-focus-visible:ring-2 group-focus-visible:ring-white">
                    <span className="flex h-8 w-8 items-center justify-center rounded-full bg-black text-white">
                      <Play className="ml-0.5 h-3.5 w-3.5 fill-current" />
                    </span>
                    Watch the demo
                    <span className="font-mono text-xs text-black/50">0:30</span>
                  </span>
                </button>
              )}

              <span
                aria-hidden
                className="pointer-events-none absolute left-1/2 top-0 -translate-x-1/2 rounded-b-[30%] bg-black"
                style={{ width: `${NOTCH.width}%`, height: `${NOTCH.height}%` }}
              />
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
