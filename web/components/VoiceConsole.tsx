"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { textQuery, voiceQuery } from "@/lib/api";
import { MicRecorder } from "@/lib/audio";
import type { QueryResponse, Transcript } from "@/lib/types";
import { AnswerPanel } from "./AnswerPanel";
import { DecisionTrace } from "./DecisionTrace";
import { LatencyPanel } from "./LatencyPanel";
import { Waveform } from "./Waveform";

const LANGUAGES = [
  { code: "", label: "Auto detect" },
  { code: "hi-IN", label: "हिन्दी" },
  { code: "bn-IN", label: "বাংলা" },
  { code: "ta-IN", label: "தமிழ்" },
  { code: "te-IN", label: "తెలుగు" },
  { code: "mr-IN", label: "मराठी" },
  { code: "en-IN", label: "English" },
];

interface Props {
  strategies: string[];
  defaultStrategy: string;
}

export function VoiceConsole({ strategies, defaultStrategy }: Props) {
  const [recording, setRecording] = useState(false);
  const [busy, setBusy] = useState(false);
  const [answer, setAnswer] = useState("");
  const [response, setResponse] = useState<QueryResponse | null>(null);
  const [transcript, setTranscript] = useState<Transcript | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [question, setQuestion] = useState("");
  const [language, setLanguage] = useState("");
  const [strategy, setStrategy] = useState(defaultStrategy);

  const recorderRef = useRef<MicRecorder | null>(null);
  const sampleLevels = useCallback(() => recorderRef.current?.levels() ?? null, []);

  useEffect(() => () => recorderRef.current?.cancel(), []);

  const reset = () => {
    setAnswer("");
    setResponse(null);
    setTranscript(null);
    setError(null);
  };

  const handlers = {
    onTranscript: (value: Transcript) => {
      setTranscript(value);
      setQuestion(value.text);
    },
    onChunk: (text: string) => setAnswer((current) => (current ? `${current} ${text}` : text)),
    onFinal: (value: QueryResponse) => {
      setResponse(value);
      if (value.answer) setAnswer(value.answer);
      if (value.transcript) setTranscript(value.transcript);
    },
    onError: (message: string) => setError(message),
  };

  const startRecording = async () => {
    reset();
    try {
      const recorder = new MicRecorder();
      await recorder.start();
      recorderRef.current = recorder;
      setRecording(true);
    } catch (cause) {
      setError(`microphone unavailable: ${String(cause)}`);
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
      await voiceQuery(blob, { strategy, language: language || undefined }, handlers);
    } catch (cause) {
      setError(String(cause));
    } finally {
      setBusy(false);
    }
  };

  const askText = async () => {
    if (!question.trim() || busy) return;
    reset();
    setBusy(true);
    try {
      await textQuery(question.trim(), { strategy, language: language || undefined }, handlers);
    } catch (cause) {
      setError(String(cause));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-4">
      <section className="rounded-xl border border-[var(--color-edge)] bg-[var(--color-panel)] p-5">
        <div className="mb-4 flex flex-wrap gap-3">
          <Select label="Language" value={language} onChange={setLanguage}>
            {LANGUAGES.map((item) => (
              <option key={item.code} value={item.code}>
                {item.label}
              </option>
            ))}
          </Select>
          <Select label="Chunking" value={strategy} onChange={setStrategy}>
            {strategies.map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </Select>
        </div>

        <Waveform active={recording} sample={sampleLevels} />

        <div className="mt-4 flex flex-wrap items-center gap-3">
          <button
            onClick={recording ? stopRecording : startRecording}
            disabled={busy && !recording}
            className={`flex items-center gap-2 rounded-full px-5 py-2.5 text-sm font-medium transition disabled:opacity-40 ${
              recording
                ? "recording-pulse bg-rose-500 text-white"
                : "bg-[var(--color-accent-soft)] text-slate-950"
            }`}
          >
            <span className={`h-2.5 w-2.5 rounded-full ${recording ? "bg-white" : "bg-slate-950"}`} />
            {recording ? "Stop and ask" : "Hold a question"}
          </button>
          <span className="text-xs text-[var(--color-muted)]">
            {recording
              ? "Recording - speak your question, then stop."
              : "Record a question or type one below."}
          </span>
        </div>

        <div className="mt-4 flex gap-2">
          <input
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            onKeyDown={(event) => event.key === "Enter" && askText()}
            placeholder="…or type a question in any supported language"
            className="flex-1 rounded-lg border border-[var(--color-edge)] bg-[var(--color-surface)] px-3 py-2 text-sm outline-none focus:border-[var(--color-accent)]"
          />
          <button
            onClick={askText}
            disabled={busy || !question.trim()}
            className="rounded-lg border border-[var(--color-edge)] px-4 py-2 text-sm text-slate-200 disabled:opacity-40"
          >
            Ask
          </button>
        </div>

        {error && (
          <p className="mt-3 rounded-lg border border-rose-500/40 bg-rose-500/10 px-3 py-2 text-xs text-rose-300">
            {error}
          </p>
        )}
      </section>

      <AnswerPanel answer={answer} streaming={busy} response={response} />
      <DecisionTrace
        transcript={transcript}
        guardrail={response?.guardrail ?? null}
        crag={response?.crag ?? null}
      />
      {response && <LatencyPanel timings={response.timings} />}
    </div>
  );
}

function Select({
  label,
  value,
  onChange,
  children,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  children: React.ReactNode;
}) {
  return (
    <label className="flex items-center gap-2 text-xs text-[var(--color-muted)]">
      {label}
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="rounded-lg border border-[var(--color-edge)] bg-[var(--color-surface)] px-2 py-1.5 text-sm text-slate-200 outline-none focus:border-[var(--color-accent)]"
      >
        {children}
      </select>
    </label>
  );
}
