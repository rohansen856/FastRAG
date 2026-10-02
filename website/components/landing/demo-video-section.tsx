"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Play } from "lucide-react";

const YOUTUBE_ID = "7SnSBCGezbU";
const EMBED_ORIGIN = "https://www.youtube-nocookie.com";
const DURATION = 30;

/** Scene starts in seconds, from the film's storyboard (brag-output/brag-plan.md). */
const CHAPTERS = [
  { start: 0, title: "Ask" },
  { start: 3.8, title: "Retrieve & rerank" },
  { start: 9.3, title: "Latency budget" },
  { start: 12.5, title: "Any language" },
  { start: 17.4, title: "Cited or silent" },
  { start: 22.9, title: "Two profiles" },
  { start: 27.3, title: "FastRAG" },
].map((chapter, index, all) => ({
  ...chapter,
  end: all[index + 1]?.start ?? DURATION,
}));

function timestamp(seconds: number): string {
  const whole = Math.floor(seconds);
  return `${Math.floor(whole / 60)}:${String(whole % 60).padStart(2, "0")}`;
}

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
 * Drives the embedded player over postMessage (the protocol behind the IFrame API), so the
 * chapter rail can follow playback and seek without loading YouTube's API script.
 */
function useYouTubeBridge(frameRef: React.RefObject<HTMLIFrameElement | null>, active: boolean) {
  const [time, setTime] = useState(0);

  const send = useCallback(
    (message: Record<string, unknown>) => {
      frameRef.current?.contentWindow?.postMessage(
        JSON.stringify({ id: 1, channel: "widget", ...message }),
        EMBED_ORIGIN,
      );
    },
    [frameRef],
  );

  useEffect(() => {
    if (!active) return;
    const onMessage = (event: MessageEvent) => {
      if (event.origin !== EMBED_ORIGIN || typeof event.data !== "string") return;
      try {
        const data = JSON.parse(event.data) as { info?: { currentTime?: unknown } };
        if (typeof data.info?.currentTime === "number") setTime(data.info.currentTime);
      } catch {
        // Not a player message.
      }
    };
    window.addEventListener("message", onMessage);
    return () => window.removeEventListener("message", onMessage);
  }, [active]);

  const listen = useCallback(() => send({ event: "listening" }), [send]);
  const seek = useCallback(
    (seconds: number) => {
      send({ event: "command", func: "seekTo", args: [seconds, true] });
      send({ event: "command", func: "playVideo", args: [] });
      setTime(seconds);
    },
    [send],
  );

  return { time, listen, seek };
}

/** A front-facing laptop drawn in CSS. Sizes are in container units, so it scales as one. */
function Laptop({ children }: { children: React.ReactNode }) {
  return (
    <div className="@container relative">
      {/* Lid: an aluminium rim around the black bezel. */}
      <div className="relative mx-[6cqw] rounded-t-[2.4cqw] rounded-b-[0.6cqw] bg-gradient-to-b from-[#e4e4e7] via-[#d2d3d7] to-[#b8b9be] p-[0.32cqw] shadow-[0_1px_0_rgba(255,255,255,0.7)_inset]">
        <div className="relative rounded-t-[2.1cqw] rounded-b-[0.4cqw] bg-[#0b0b0c] px-[1.5cqw] pb-[1.9cqw] pt-[1.9cqw]">
          <span
            aria-hidden
            className="absolute left-1/2 top-[0.7cqw] h-[0.55cqw] w-[0.55cqw] -translate-x-1/2 rounded-full bg-[#1d2a33] ring-1 ring-white/5"
          />
          <div className="relative aspect-video overflow-hidden rounded-[0.35cqw] bg-black">
            {children}
          </div>
        </div>
      </div>

      {/* Hinge, then the base seen edge-on with its thumb scoop. */}
      <div className="mx-[7.5cqw] h-[0.7cqw] bg-gradient-to-b from-[#1b1b1d] to-[#56575c]" />
      <div className="relative h-[2.2cqw] rounded-b-[1.6cqw] rounded-t-[0.25cqw] bg-gradient-to-b from-[#ececee] via-[#d4d5d9] to-[#a3a4a9] shadow-[0_1px_0_rgba(255,255,255,0.9)_inset]">
        <span
          aria-hidden
          className="absolute left-1/2 top-0 h-[0.9cqw] w-[13cqw] -translate-x-1/2 rounded-b-[1cqw] bg-gradient-to-b from-[#b4b5ba] to-[#cfd0d4]"
        />
      </div>

      {/* Contact shadow on the floor. */}
      <div
        aria-hidden
        className="pointer-events-none mx-auto -mt-[0.6cqw] h-[2.4cqw] w-[86%] rounded-[50%] bg-foreground/20 blur-[1.2cqw]"
      />
    </div>
  );
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

/**
 * The launch film on a CSS laptop. Nothing from YouTube loads with the page: the screen shows
 * a self-hosted poster frame, and the youtube-nocookie player iframe is created only when the
 * visitor presses play or picks a chapter. Hovering or focusing either warms the connection.
 */
export function DemoVideoSection() {
  const [isVisible, setIsVisible] = useState(false);
  const [startAt, setStartAt] = useState<number | null>(null);
  const sectionRef = useRef<HTMLElement>(null);
  const frameRef = useRef<HTMLIFrameElement>(null);
  const playing = startAt !== null;
  const { time, listen, seek } = useYouTubeBridge(frameRef, playing);

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

  const playFrom = (seconds: number) => {
    if (playing) seek(seconds);
    else setStartAt(seconds);
  };

  const embedSrc = (seconds: number) => {
    const params = new URLSearchParams({
      autoplay: "1",
      rel: "0",
      playsinline: "1",
      enablejsapi: "1",
      origin: window.location.origin,
      start: String(Math.floor(seconds)),
    });
    return `${EMBED_ORIGIN}/embed/${YOUTUBE_ID}?${params}`;
  };

  return (
    <section id="demo" ref={sectionRef} className="relative py-24 lg:py-32">
      <div className="max-w-[1400px] mx-auto px-6 lg:px-12">
        <div className="mb-12 grid gap-8 lg:mb-16 lg:grid-cols-2 lg:items-end">
          <div>
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
          <p
            className={`max-w-md text-muted-foreground leading-relaxed transition-all duration-700 delay-150 lg:justify-self-end ${
              isVisible ? "opacity-100 translate-y-0" : "opacity-0 translate-y-4"
            }`}
          >
            One question through the whole pipeline: retrieval and rerank, the latency budget,
            multilingual answers, citations and refusals. Jump to any part below.
          </p>
        </div>

        <figure
          className={`relative border border-foreground/10 transition-all duration-1000 delay-200 ${
            isVisible ? "opacity-100 translate-y-0" : "opacity-0 translate-y-8"
          }`}
        >
          <CornerTicks />
          <div
            aria-hidden
            className="pointer-events-none absolute inset-0 opacity-60 [mask-image:radial-gradient(ellipse_at_center,black_30%,transparent_75%)]"
            style={{
              backgroundImage:
                "linear-gradient(to right, color-mix(in oklch, var(--foreground) 7%, transparent) 1px, transparent 1px), linear-gradient(to bottom, color-mix(in oklch, var(--foreground) 7%, transparent) 1px, transparent 1px)",
              backgroundSize: "48px 48px",
            }}
          />

          <div className="relative flex items-center justify-between gap-4 border-b border-foreground/10 px-4 py-3 font-mono text-[11px] uppercase tracking-widest text-muted-foreground lg:px-6">
            <span>Fig. 01 — Launch film</span>
            <span className="hidden sm:inline">1080p · 0:30</span>
          </div>

          <div className="relative px-4 pb-6 pt-10 sm:px-10 lg:px-16 lg:pt-14">
            <div
              className="mx-auto w-full"
              style={{ maxWidth: "min(820px, calc((100svh - 17rem) * 1.75))" }}
            >
              <Laptop>
                {playing ? (
                  <iframe
                    ref={frameRef}
                    src={embedSrc(startAt)}
                    onLoad={listen}
                    title="FastRAG demo video"
                    allow="autoplay; encrypted-media; picture-in-picture; fullscreen"
                    allowFullScreen
                    referrerPolicy="strict-origin-when-cross-origin"
                    className="absolute inset-0 h-full w-full border-0"
                  />
                ) : (
                  <button
                    type="button"
                    onClick={() => playFrom(0)}
                    onPointerEnter={warmConnections}
                    onFocus={warmConnections}
                    aria-label="Play the FastRAG demo video"
                    className="group absolute inset-0 flex items-center justify-center outline-none"
                  >
                    <img
                      src="/demo/fastrag-demo-poster.webp"
                      alt=""
                      width={1600}
                      height={900}
                      loading="lazy"
                      decoding="async"
                      className="absolute inset-0 h-full w-full object-cover"
                    />
                    <span
                      aria-hidden
                      className="absolute inset-0 bg-black/30 transition-colors duration-300 group-hover:bg-black/15"
                    />
                    <span
                      aria-hidden
                      className="absolute inset-0 bg-[linear-gradient(115deg,rgba(255,255,255,0.09)_0%,transparent_38%)]"
                    />
                    <span className="relative flex items-center gap-3 rounded-full bg-background/95 p-1.5 text-sm sm:py-2 sm:pl-2 sm:pr-4 text-foreground shadow-lg ring-1 ring-foreground/10 transition-transform duration-300 group-hover:scale-105 group-focus-visible:ring-2 group-focus-visible:ring-background">
                      <span className="flex h-8 w-8 items-center justify-center rounded-full bg-foreground text-background">
                        <Play className="ml-0.5 h-3.5 w-3.5 fill-current" />
                      </span>
                      <span className="hidden sm:inline">Watch the demo</span>
                      <span className="hidden font-mono text-xs text-muted-foreground sm:inline">0:30</span>
                    </span>
                  </button>
                )}
              </Laptop>
            </div>
          </div>

          <ol className="relative flex snap-x overflow-x-auto border-t border-foreground/10 [scrollbar-width:none]">
            {CHAPTERS.map((chapter, index) => {
              const progress = playing
                ? Math.min(1, Math.max(0, (time - chapter.start) / (chapter.end - chapter.start)))
                : 0;
              const current = playing && time >= chapter.start && time < chapter.end;
              return (
                <li
                  key={chapter.title}
                  className="shrink-0 snap-start border-foreground/10 [&:not(:last-child)]:border-r lg:min-w-0 lg:shrink"
                  style={{ flexGrow: chapter.end - chapter.start, flexBasis: 0 }}
                >
                  <button
                    type="button"
                    onClick={() => playFrom(chapter.start)}
                    onPointerEnter={warmConnections}
                    onFocus={warmConnections}
                    aria-label={`Play from ${timestamp(chapter.start)}, ${chapter.title}`}
                    className="group relative flex w-full flex-col gap-1.5 px-4 py-4 text-left transition-colors hover:bg-foreground/[0.03] focus-visible:bg-foreground/[0.04] focus-visible:outline-none lg:px-5"
                  >
                    <span aria-hidden className="absolute inset-x-0 top-0 h-px bg-foreground/10">
                      <span
                        className="block h-full bg-foreground transition-[width] duration-300 ease-linear"
                        style={{ width: `${progress * 100}%` }}
                      />
                    </span>
                    <span className="whitespace-nowrap font-mono text-[11px] text-muted-foreground">
                      {String(index + 1).padStart(2, "0")} · {timestamp(chapter.start)}
                    </span>
                    <span
                      className={`whitespace-nowrap text-sm transition-colors lg:truncate ${
                        current ? "text-foreground" : "text-foreground/70 group-hover:text-foreground"
                      }`}
                    >
                      {chapter.title}
                    </span>
                  </button>
                </li>
              );
            })}
          </ol>
        </figure>
      </div>
    </section>
  );
}
