"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Loader2, Mic, Paperclip, Settings, Square, X } from "lucide-react";
import { ingestDocument, deleteDocument, textQuery, voiceQuery } from "@/lib/api";
import { MAX_ATTACHMENTS, UPLOAD_ACCEPT, validateUploadFile } from "@/lib/upload";
import { MicRecorder } from "@/lib/audio";
import type { IngestResult, QueryResponse, Transcript } from "@/lib/types";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { AnimatedSphere } from "./animated-sphere";
import { AnswerChatSection } from "./answer-chat-section";
import { FileTypeIcon } from "./file-type-icon";

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
type ScopeMode = "document" | "corpus";

type PendingUpload = {
  id: string;
  filename: string;
};

function ScopeSettings({
  scopeMode,
  onScopeChange,
}: {
  scopeMode: ScopeMode;
  onScopeChange: (mode: ScopeMode) => void;
}) {
  return (
    <Popover>
      <PopoverTrigger asChild>
        <button
          type="button"
          aria-label="Search scope settings"
          className={`inline-flex h-[26px] w-[26px] items-center justify-center rounded-full border border-foreground/15 bg-background/60 transition-colors hover:bg-background/80 ${
            scopeMode === "corpus" ? "text-foreground" : "text-muted-foreground"
          }`}
        >
          <Settings className="h-3.5 w-3.5" />
        </button>
      </PopoverTrigger>
      <PopoverContent align="start" className="w-52 p-2 text-xs font-mono">
        <p className="px-2 py-1 text-[10px] uppercase tracking-widest text-muted-foreground">
          Search scope
        </p>
        <button
          type="button"
          onClick={() => onScopeChange("document")}
          className={`flex w-full rounded-md px-2 py-2 text-left transition-colors ${
            scopeMode === "document"
              ? "bg-foreground text-background"
              : "text-foreground hover:bg-foreground/5"
          }`}
        >
          Attached files
        </button>
        <button
          type="button"
          onClick={() => onScopeChange("corpus")}
          className={`mt-0.5 flex w-full rounded-md px-2 py-2 text-left transition-colors ${
            scopeMode === "corpus"
              ? "bg-foreground text-background"
              : "text-foreground hover:bg-foreground/5"
          }`}
        >
          Entire corpus
        </button>
      </PopoverContent>
    </Popover>
  );
}

function AttachmentChip({
  filename,
  loading = false,
  onRemove,
}: {
  filename: string;
  loading?: boolean;
  onRemove?: () => void;
}) {
  return (
    <span className="relative inline-flex items-center gap-1.5 rounded-full border border-foreground/15 bg-background/60 px-2.5 py-1">
      <span className="relative flex h-4 w-4 items-center justify-center">
        <FileTypeIcon filename={filename} disabled={loading} />
        {loading && (
          <Loader2
            className="absolute h-3 w-3 animate-spin text-foreground/70"
            aria-label="Indexing document"
          />
        )}
      </span>
      {!loading && onRemove && (
        <button
          type="button"
          onClick={onRemove}
          aria-label="Remove attachment"
          className="text-muted-foreground hover:text-foreground"
        >
          <X className="w-3 h-3" />
        </button>
      )}
    </span>
  );
}

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
  const [attachedDocs, setAttachedDocs] = useState<IngestResult[]>([]);
  const [pendingUploads, setPendingUploads] = useState<PendingUpload[]>([]);
  const [scopeMode, setScopeMode] = useState<ScopeMode>("document");

  const uploading = pendingUploads.length > 0;

  const recorderRef = useRef<MicRecorder | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const attachedDocsRef = useRef(attachedDocs);
  attachedDocsRef.current = attachedDocs;
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

  useEffect(() => {
    const purge = () => {
      for (const doc of attachedDocsRef.current) {
        void deleteDocument(doc.document_id);
      }
    };
    window.addEventListener("pagehide", purge);
    return () => {
      window.removeEventListener("pagehide", purge);
      purge();
    };
  }, []);

  const queryOptions = useCallback(
    () => ({
      strategy: DEFAULT_STRATEGY,
      language: DEFAULT_LANGUAGE || undefined,
      documentIds:
        attachedDocs.length && scopeMode === "document"
          ? attachedDocs.map((doc) => doc.document_id)
          : undefined,
    }),
    [attachedDocs, scopeMode],
  );

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
      await voiceQuery(blob, queryOptions(), handlers);
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
      await textQuery(asked, queryOptions(), handlers);
    } catch (cause) {
      setError(friendlyError(String(cause)));
    } finally {
      setBusy(false);
    }
  };

  const onFileSelected = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(event.target.files ?? []);
    event.target.value = "";
    if (!files.length) return;

    const remaining = MAX_ATTACHMENTS - attachedDocs.length;
    if (remaining <= 0) {
      setError(`You can attach up to ${MAX_ATTACHMENTS} files.`);
      return;
    }
    const batch = files.slice(0, remaining);
    if (files.length > remaining) {
      setError(`Only ${remaining} more file${remaining === 1 ? "" : "s"} can be attached.`);
    } else {
      setError(null);
    }

    for (const file of batch) {
      const rejection = validateUploadFile(file);
      if (rejection) {
        setError(rejection);
        return;
      }
    }

    const pending = batch.map((file) => ({
      id: crypto.randomUUID(),
      filename: file.name,
    }));
    setPendingUploads((current) => [...current, ...pending]);
    try {
      for (let index = 0; index < batch.length; index += 1) {
        const result = await ingestDocument(batch[index]);
        setAttachedDocs((current) => [...current, result]);
        setPendingUploads((current) => current.filter((item) => item.id !== pending[index].id));
      }
      setScopeMode("document");
    } catch (cause) {
      setPendingUploads((current) =>
        current.filter((item) => !pending.some((entry) => entry.id === item.id)),
      );
      setError(friendlyError(String(cause)));
    }
  };

  const removeAttachment = (documentId: string) => {
    setAttachedDocs((current) => current.filter((doc) => doc.document_id !== documentId));
    void deleteDocument(documentId).catch(() => {
      // Best-effort cleanup; vectors are removed when the session ends.
    });
  };

  const clearAttachments = () => {
    for (const doc of attachedDocs) {
      void deleteDocument(doc.document_id).catch(() => undefined);
    }
    setAttachedDocs([]);
    setPendingUploads([]);
    setScopeMode("document");
  };

  const hasAttachments = attachedDocs.length > 0 || pendingUploads.length > 0;
  const attachmentCount = attachedDocs.length + pendingUploads.length;

  const status = (() => {
    if (error) return <span className="text-rose-600">{error}</span>;
    if (recording) return "Recording - speak your question, then stop.";
    if (busy) return <ThinkingWave />;
    if (hasAttachments) {
      return (
        <div className="flex flex-wrap items-center gap-2">
          <ScopeSettings scopeMode={scopeMode} onScopeChange={setScopeMode} />
          {attachedDocs.map((doc) => (
            <AttachmentChip
              key={doc.document_id}
              filename={doc.title}
              onRemove={() => removeAttachment(doc.document_id)}
            />
          ))}
          {pendingUploads.map((pending) => (
            <AttachmentChip key={pending.id} filename={pending.filename} loading />
          ))}
          {attachmentCount > 1 && (
            <button
              type="button"
              onClick={clearAttachments}
              className="text-xs font-mono text-muted-foreground hover:text-foreground"
            >
              Clear all
            </button>
          )}
        </div>
      );
    }
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
                ref={fileInputRef}
                type="file"
                accept={UPLOAD_ACCEPT}
                multiple
                className="hidden"
                onChange={onFileSelected}
              />
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                disabled={busy || uploading}
                aria-label="Attach document"
                className="ml-2 flex items-center justify-center w-10 h-10 rounded-full text-muted-foreground hover:text-foreground hover:bg-foreground/5 transition-colors disabled:opacity-40"
              >
                <Paperclip className="w-4 h-4" />
              </button>
              <span
                className="h-6 w-px shrink-0 bg-foreground/15"
                aria-hidden
              />
              <input
                type="text"
                value={question}
                onChange={(event) => setQuestion(event.target.value)}
                onKeyDown={(event) => event.key === "Enter" && askText()}
                disabled={(busy && !recording) || uploading}
                placeholder="Type it here or say it out loud..."
                className="flex-1 h-full bg-transparent px-3 pr-16 text-base outline-none placeholder:text-muted-foreground disabled:opacity-50"
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

            <div className="mt-2 ml-6 min-h-5 text-xs text-muted-foreground">{status}</div>
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
      attachedCount={attachedDocs.length}
      scopeMode={attachedDocs.length ? scopeMode : null}
    />
    </>
  );
}
