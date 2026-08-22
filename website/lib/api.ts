import type { IngestResult, QueryOptions, QueryResponse, Transcript } from "./types";
import { validateUploadFile } from "./upload";

export interface StreamHandlers {
  onTranscript?: (transcript: Transcript) => void;
  onChunk?: (text: string) => void;
  onFinal?: (response: QueryResponse) => void;
  onError?: (message: string) => void;
}

/**
 * Reads an SSE stream from the proxy route.
 *
 * `EventSource` cannot issue POST requests, so the stream is read from `fetch`
 * and the wire format is parsed here. Events are separated by a blank line and
 * a single event may carry several `data:` lines.
 */
export async function streamEvents(
  path: string,
  body: BodyInit,
  headers: HeadersInit,
  handlers: StreamHandlers,
  signal?: AbortSignal,
): Promise<void> {
  const response = await fetch(`/api/rag/${path}`, { method: "POST", body, headers, signal });
  if (!response.ok || !response.body) {
    const detail = await response.text().catch(() => response.statusText);
    handlers.onError?.(detail || `request failed with ${response.status}`);
    return;
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    // Upstream may emit CRLF (Starlette/uvicorn). Normalize so frame splits work.
    buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, "\n").replace(/\r/g, "\n");

    let boundary = buffer.indexOf("\n\n");
    while (boundary !== -1) {
      dispatch(buffer.slice(0, boundary), handlers);
      buffer = buffer.slice(boundary + 2);
      boundary = buffer.indexOf("\n\n");
    }
  }
  if (buffer.trim()) dispatch(buffer, handlers);
}

function dispatch(frame: string, handlers: StreamHandlers): void {
  let event = "message";
  const dataLines: string[] = [];
  for (const line of frame.split("\n")) {
    if (line.startsWith("event:")) event = line.slice(6).trim();
    else if (line.startsWith("data:")) dataLines.push(line.slice(5).trim());
  }
  if (!dataLines.length) return;

  let payload: unknown;
  try {
    payload = JSON.parse(dataLines.join("\n"));
  } catch {
    return;
  }

  switch (event) {
    case "transcript":
      handlers.onTranscript?.(payload as Transcript);
      break;
    case "answer_chunk":
      handlers.onChunk?.((payload as { text: string }).text);
      break;
    case "final":
      handlers.onFinal?.(payload as QueryResponse);
      break;
    case "error": {
      const detail = payload as { stage?: string; message?: string; detail?: string };
      handlers.onError?.(
        detail.message ? `${detail.stage ?? "pipeline"}: ${detail.message}` : String(detail.detail),
      );
      break;
    }
  }
}

export async function ingestDocument(file: File, title?: string): Promise<IngestResult> {
  const rejection = validateUploadFile(file);
  if (rejection) throw new Error(rejection);
  const form = new FormData();
  form.append("file", file, file.name);
  if (title) form.append("title", title);
  const response = await fetch("/api/rag/v1/documents/ingest", { method: "POST", body: form });
  if (!response.ok) {
    const detail = await response.text().catch(() => response.statusText);
    throw new Error(detail || `upload failed with ${response.status}`);
  }
  return (await response.json()) as IngestResult;
}

export async function deleteDocument(documentId: string): Promise<void> {
  const response = await fetch(`/api/rag/v1/documents/${encodeURIComponent(documentId)}`, {
    method: "DELETE",
    keepalive: true,
  });
  if (!response.ok) {
    const detail = await response.text().catch(() => response.statusText);
    throw new Error(detail || `delete failed with ${response.status}`);
  }
}

function queryPayload(query: string, options: QueryOptions) {
  const documentIds =
    options.documentIds?.length
      ? options.documentIds
      : options.documentId
        ? [options.documentId]
        : null;
  return JSON.stringify({
    query,
    strategy: options.strategy ?? null,
    language: options.language ?? null,
    document_id: documentIds?.length === 1 ? documentIds[0] : null,
    document_ids: documentIds && documentIds.length > 1 ? documentIds : null,
  });
}

export async function textQuery(
  query: string,
  options: QueryOptions,
  handlers: StreamHandlers,
  signal?: AbortSignal,
): Promise<void> {
  await streamEvents(
    "v1/query/stream",
    queryPayload(query, options),
    { "content-type": "application/json" },
    handlers,
    signal,
  );
}

export async function voiceQuery(
  audio: Blob,
  options: QueryOptions,
  handlers: StreamHandlers,
  signal?: AbortSignal,
): Promise<void> {
  const form = new FormData();
  form.append("file", audio, "question.wav");
  if (options.strategy) form.append("strategy", options.strategy);
  if (options.language) form.append("language", options.language);
  const documentIds =
    options.documentIds?.length
      ? options.documentIds
      : options.documentId
        ? [options.documentId]
        : null;
  if (documentIds?.length === 1) form.append("document_id", documentIds[0]);
  else if (documentIds && documentIds.length > 1) form.append("document_ids", documentIds.join(","));
  // Let the browser set the multipart boundary.
  await streamEvents("v1/voice/query/stream", form, {}, handlers, signal);
}

export async function runComparison(
  query: string,
  strategies: string[],
): Promise<Record<string, QueryResponse | { error: string }>> {
  const entries = await Promise.all(
    strategies.map(async (strategy) => {
      try {
        const response = await fetch("/api/rag/v1/query", {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({ query, strategy }),
        });
        if (!response.ok) {
          return [strategy, { error: await response.text() }] as const;
        }
        return [strategy, (await response.json()) as QueryResponse] as const;
      } catch (error) {
        return [strategy, { error: String(error) }] as const;
      }
    }),
  );
  return Object.fromEntries(entries);
}
