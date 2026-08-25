import type { QueryResponse } from "@/lib/types";

const PREFIX = "fastrag:trace:";
const INDEX_KEY = "fastrag:trace:index";
const MAX_TRACES = 10;

export interface StoredQueryTrace {
  question: string;
  response: QueryResponse;
  savedAt: number;
  scopeMode?: "document" | "corpus";
  attachedCount?: number;
}

function traceKey(queryId: string): string {
  return `${PREFIX}${queryId}`;
}

function readIndex(): string[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = sessionStorage.getItem(INDEX_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as unknown;
    return Array.isArray(parsed) ? parsed.filter((id): id is string => typeof id === "string") : [];
  } catch {
    return [];
  }
}

function writeIndex(ids: string[]): void {
  sessionStorage.setItem(INDEX_KEY, JSON.stringify(ids.slice(0, MAX_TRACES)));
}

export function saveQueryTrace(
  question: string,
  response: QueryResponse,
  meta?: Pick<StoredQueryTrace, "scopeMode" | "attachedCount">,
): void {
  if (typeof window === "undefined" || !response.query_id) return;
  const entry: StoredQueryTrace = {
    question,
    response,
    savedAt: Date.now(),
    ...meta,
  };
  sessionStorage.setItem(traceKey(response.query_id), JSON.stringify(entry));
  const ids = readIndex().filter((id) => id !== response.query_id);
  ids.unshift(response.query_id);
  writeIndex(ids);
}

export function loadQueryTrace(queryId: string): StoredQueryTrace | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = sessionStorage.getItem(traceKey(queryId));
    if (!raw) return null;
    return JSON.parse(raw) as StoredQueryTrace;
  } catch {
    return null;
  }
}

export function listRecentTraces(): StoredQueryTrace[] {
  return readIndex()
    .map((id) => loadQueryTrace(id))
    .filter((entry): entry is StoredQueryTrace => entry !== null);
}
