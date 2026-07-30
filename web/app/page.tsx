import { BenchDashboard } from "@/components/BenchDashboard";
import { StrategyCompare } from "@/components/StrategyCompare";
import { VoiceConsole } from "@/components/VoiceConsole";

const FALLBACK_STRATEGIES = [
  "fixed",
  "sentence",
  "sentence_window",
  "semantic",
  "hierarchical",
  "metadata_aware",
];

interface StrategyInfo {
  available: string[];
  indexed: string[];
  default: string;
}

/**
 * Fetched server-side so the page renders with the strategies that are actually
 * indexed. The API is not reachable at build time, so this must not be cached.
 */
async function loadStrategies(): Promise<StrategyInfo> {
  const url = process.env.FASTRAG_API_URL ?? "http://localhost:8000";
  const token = process.env.FASTRAG_QUERY_TOKEN ?? "";
  try {
    const response = await fetch(`${url.replace(/\/$/, "")}/v1/strategies`, {
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
    });
    if (!response.ok) throw new Error(String(response.status));
    const info = (await response.json()) as StrategyInfo;
    if (info.indexed?.length) return info;
    return { ...info, indexed: FALLBACK_STRATEGIES };
  } catch {
    return {
      available: FALLBACK_STRATEGIES,
      indexed: FALLBACK_STRATEGIES,
      default: "sentence",
    };
  }
}

export default async function Home() {
  const { indexed, default: defaultStrategy } = await loadStrategies();

  return (
    <main className="mx-auto max-w-5xl px-5 py-10">
      <header className="mb-8">
        <h1 className="text-2xl font-semibold text-slate-100">FastRAG</h1>
        <p className="mt-1 max-w-2xl text-sm text-[var(--color-muted)]">
          Voice-enabled retrieval over MS MARCO passages in Hindi, Bengali, Tamil, Telugu, Marathi
          and English. Every sentence is checked against its source before it reaches you, and the
          pipeline abstains rather than guessing when retrieval is weak.
        </p>
      </header>

      <VoiceConsole strategies={indexed} defaultStrategy={defaultStrategy} />

      <div className="mt-6 space-y-6">
        <StrategyCompare strategies={indexed} />
        <BenchDashboard />
      </div>

      <footer className="mt-10 border-t border-[var(--color-edge)] pt-4 text-xs text-[var(--color-muted)]">
        Answers are generated only from retrieved sources. An abstention is a correct answer when
        the corpus does not contain one.
      </footer>
    </main>
  );
}
