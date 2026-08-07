"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Mic, Square } from "lucide-react";
import { textQuery, voiceQuery } from "@/lib/api";
import { MicRecorder } from "@/lib/audio";
import type { QueryResponse, Transcript } from "@/lib/types";
import { AnimatedSphere } from "./animated-sphere";
import { AnswerChatSection } from "./answer-chat-section";

const words = [
  "English",
  "हिन्दी",
  "मराठी",
  "संस्कृतम्",
  "नेपाली",
  "বাংলা",
  "অসমীয়া",
  "ਪੰਜਾਬੀ",
  "ગુજરાતી",
  "ଓଡ଼ିଆ",
  "தமிழ்",
  "తెలుగు",
  "ಕನ್ನಡ",
  "മലയാളം",
  "اردو",
];

/** Same defaults as the old VoiceConsole when language/strategy selectors are absent. */
const DEFAULT_STRATEGY = "sentence";
const DEFAULT_LANGUAGE = "";

function friendlyError(raw: string): string {
  const text = raw.trim();
  let detail = text;
  try {
    const parsed = JSON.parse(text) as { detail?: unknown; error?: unknown };
    if (typeof parsed.detail === "string") detail = parsed.detail;
    else if (typeof parsed.error === "string") detail = parsed.error;
  } catch {
    // plain string
  }
  const lower = `${detail} ${text}`.toLowerCase();
  if (
    lower.includes("cannot reach") ||
    lower.includes("fetch failed") ||
    lower.includes("econnrefused") ||
    lower.includes("networkerror")
  ) {
    return "Can't reach the API right now. Start the FastRAG server and try again.";
  }
  if (lower.includes("microphone") || lower.includes("notallowederror") || lower.includes("permission")) {
    return "Microphone access was blocked. Allow it in the browser and try again.";
  }
  if (lower.includes("query_token") || lower.includes("not configured")) {
    return "This site isn't configured to talk to the API yet.";
  }
  if (lower.includes("no text") || lower.includes("transcription returned")) {
    return "Didn't catch that. Try speaking again a bit closer to the mic.";
  }
  if (detail && detail.length < 160 && !detail.trimStart().startsWith("{")) {
    return detail;
  }
  return "Something went wrong. Try again in a moment.";
}

function ThinkingWave() {
  return (
    <span className="inline-flex" aria-label="Thinking">
      {"Thinking…".split("").map((char, i) => (
        <span
          key={`${char}-${i}`}
          className="animate-thinking-wave"
          style={{ animationDelay: `${i * 70}ms` }}
        >
          {char === " " ? "\u00a0" : char}
        </span>
      ))}
    </span>
  );
}

export function HeroSection() {
  const [isVisible, setIsVisible] = useState(false);
  const [wordIndex, setWordIndex] = useState(0);

  const [recording, setRecording] = useState(false);
  const [busy, setBusy] = useState(false);
  const [question, setQuestion] = useState("");
  const [askedQuestion, setAskedQuestion] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [answer, setAnswer] = useState("");
  const [response, setResponse] = useState<QueryResponse | null>(null);

  const recorderRef = useRef<MicRecorder | null>(null);
  const sampleLevels = useCallback(() => recorderRef.current?.levels() ?? null, []);

  useEffect(() => {
    setIsVisible(true);
  }, []);

  useEffect(() => {
    const interval = setInterval(() => {
      setWordIndex((prev) => (prev + 1) % words.length);
    }, 2500);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => () => recorderRef.current?.cancel(), []);

  const reset = () => {
    setAnswer("");
    setResponse(null);
    setError(null);
  };

  const handlers = {
    onTranscript: (value: Transcript) => {
      setQuestion(value.text);
      setAskedQuestion(value.text);
    },
    onChunk: (text: string) => setAnswer((current) => (current ? `${current} ${text}` : text)),
    onFinal: (value: QueryResponse) => {
      setResponse(value);
      if (value.transcript) {
        setQuestion(value.transcript.text);
        setAskedQuestion(value.transcript.text);
      }
      if (value.answer) setAnswer(value.answer);
    },
    onError: (message: string) => setError(friendlyError(message)),
  };

  const startRecording = async () => {
    reset();
    setAskedQuestion("");
    try {
      const recorder = new MicRecorder();
      await recorder.start();
      recorderRef.current = recorder;
      setRecording(true);
    } catch (cause) {
      setError(friendlyError(`microphone unavailable: ${String(cause)}`));
    }
  };

  const stopRecording = async () => {
    const recorder = recorderRef.current;
    if (!recorder) return;
    setRecording(false);
    setBusy(true);
    try {
      const { blob } = await recorder.stop();
      recorderRef.current = null;
      await voiceQuery(
        blob,
        { strategy: DEFAULT_STRATEGY, language: DEFAULT_LANGUAGE || undefined },
        handlers,
      );
    } catch (cause) {
      setError(friendlyError(String(cause)));
    } finally {
      setBusy(false);
    }
  };

  const askText = async () => {
    if (!question.trim() || busy) return;
    const asked = question.trim();
    reset();
    setAskedQuestion(asked);
    setBusy(true);
    try {
      await textQuery(
        asked,
        { strategy: DEFAULT_STRATEGY, language: DEFAULT_LANGUAGE || undefined },
        handlers,
      );
    } catch (cause) {
      setError(friendlyError(String(cause)));
    } finally {
      setBusy(false);
    }
  };

  const status = (() => {
    if (error) return <span className="text-rose-600">{error}</span>;
    if (recording) return "Recording - speak your question, then stop.";
    if (busy) return <ThinkingWave />;
    return "Record a question or type one and press Enter.";
  })();

  return (
    <>
    <section className="relative min-h-screen w-full flex flex-col justify-center overflow-x-hidden">
      <div className="pointer-events-none absolute right-0 top-1/2 z-0 h-[600px] w-[600px] -translate-y-1/2 opacity-40 lg:h-[800px] lg:w-[800px]">
        <AnimatedSphere active={recording} sample={sampleLevels} />
      </div>

      <div className="absolute inset-0 overflow-hidden pointer-events-none opacity-30">
        {[...Array(8)].map((_, i) => (
          <div
            key={`h-${i}`}
            className="absolute h-px bg-foreground/10"
            style={{
              top: `${12.5 * (i + 1)}%`,
              left: 0,
              right: 0,
            }}
          />
        ))}
        {[...Array(12)].map((_, i) => (
          <div
            key={`v-${i}`}
            className="absolute w-px bg-foreground/10"
            style={{
              left: `${8.33 * (i + 1)}%`,
              top: 0,
              bottom: 0,
            }}
          />
        ))}
      </div>

      <div className="relative z-10 mx-auto lg:mx-32 px-6 lg:px-12 py-32 lg:py-40">
        <div
          className={`mb-8 transition-all duration-700 ${
            isVisible ? "opacity-100 translate-y-0" : "opacity-0 translate-y-4"
          }`}
        >
          <span className="inline-flex items-center gap-3 text-sm font-mono text-muted-foreground">
            <span className="w-8 h-px bg-foreground/30" />
            The platform for modern questions
          </span>
        </div>

        <div className="mb-12">
          <h1
            className={`text-left text-[clamp(3rem,12vw,10rem)] font-display leading-[0.9] tracking-tight transition-all duration-1000 ${
              isVisible ? "opacity-100 translate-y-0" : "opacity-0 translate-y-8"
            }`}
          >
            <span className="block">Ask anything</span>

            <span className="block">
              <span>in</span>{" "}
              {/* Grid stacks every word to reserve max width without .length hacks. */}
              <span className="relative inline-grid align-baseline font-indic font-bold">
                {words.map((word) => (
                  <span
                    key={`sizer-${word}`}
                    className="invisible col-start-1 row-start-1 whitespace-nowrap"
                    aria-hidden
                  >
                    {word}
                  </span>
                ))}

                <span
                  key={wordIndex}
                  className="col-start-1 row-start-1 whitespace-nowrap animate-word-in"
                >
                  {words[wordIndex]}
                </span>

                <span className="absolute -bottom-2 left-0 w-full h-3 bg-foreground/10" />
              </span>
            </span>
          </h1>
        </div>

        <div className="grid lg:grid-cols-2 gap-12 lg:gap-24 items-end">
          <div
            className={`w-full max-w-md transition-all duration-700 delay-300 ${
              isVisible ? "opacity-100 translate-y-0" : "opacity-0 translate-y-4"
            }`}
          >
            <div className="relative flex items-center h-16 rounded-full border border-foreground/15 bg-background/80 backdrop-blur-md shadow-sm focus-within:border-foreground/30 focus-within:shadow-md transition-all">
              <input
                type="text"
                value={question}
                onChange={(event) => setQuestion(event.target.value)}
                onKeyDown={(event) => event.key === "Enter" && askText()}
                disabled={busy && !recording}
                placeholder="Type it here or say it out loud..."
                className="flex-1 h-full bg-transparent px-6 pr-16 text-base outline-none placeholder:text-muted-foreground disabled:opacity-50"
              />

              <button
                type="button"
                onClick={recording ? stopRecording : startRecording}
                disabled={busy && !recording}
                aria-label={recording ? "Stop and ask" : "Hold a question"}
                className={`absolute right-2 flex items-center justify-center w-12 h-12 rounded-full transition-transform disabled:opacity-40 ${
                  recording
                    ? "recording-pulse bg-rose-500 text-white hover:scale-105"
                    : "bg-foreground text-background hover:scale-105"
                }`}
              >
                {recording ? <Square className="w-4 h-4 fill-current" /> : <Mic className="w-5 h-5" />}
              </button>
            </div>

            <p className="mt-2 ml-6 text-xs text-muted-foreground">{status}</p>
          </div>
        </div>
      </div>

      <div
        className={`absolute bottom-24 left-0 right-0 overflow-hidden transition-all duration-700 delay-500 ${
          isVisible ? "opacity-100" : "opacity-0"
        }`}
      >
        <div className="flex w-max gap-16 marquee whitespace-nowrap">
          {[...Array(2)].map((_, i) => (
            <div key={i} className="flex shrink-0 gap-16">
              {[
                { value: "<200ms", label: "retrieval pipeline", tag: "LOCAL" },
                { value: "6", label: "languages indexed", tag: "MSMARCO-XI" },
                { value: "CRAG", label: "grades before generate", tag: "ABSTAIN" },
                { value: "6", label: "chunking strategies", tag: "COMPARE" },
                { value: "Voice", label: "speak in, cite out", tag: "SARVAM" },
                { value: "2", label: "provider profiles", tag: "LOCAL · CLOUD" },
              ].map((stat) => (
                <div key={`${stat.tag}-${i}`} className="flex items-baseline gap-4">
                  <span className="text-4xl lg:text-5xl font-display">{stat.value}</span>
                  <span className="text-sm text-muted-foreground">
                    {stat.label}
                    <span className="block font-mono text-xs mt-1">{stat.tag}</span>
                  </span>
                </div>
              ))}
            </div>
          ))}
        </div>
      </div>
    </section>

    <AnswerChatSection
      question={askedQuestion}
      answer={answer}
      streaming={busy && !recording}
      response={response}
      error={error}
    />
    </>
  );
}
