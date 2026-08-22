import { NextRequest } from "next/server";

/**
 * Server-side proxy to the FastRAG API.
 *
 * The query token is a shared secret, so it must never reach the browser. Every
 * call goes through this handler, which injects the bearer token from a
 * server-only environment variable. It also means the browser talks to its own
 * origin, so the backend's CORS configuration stops mattering for the UI.
 */

const API_URL = process.env.FASTRAG_API_URL ?? "http://localhost:8000";
const API_TOKEN = process.env.FASTRAG_QUERY_TOKEN ?? "";

// Streaming responses must not be buffered or statically optimised.
export const dynamic = "force-dynamic";
export const runtime = "nodejs";

/** Match `src/fastrag/documents.py` MAX_UPLOAD_BYTES */
const MAX_UPLOAD_BYTES = 10 * 1024 * 1024;

const ALLOWED_PREFIXES = [
  "v1/query",
  "v1/query/stream",
  "v1/transcribe",
  "v1/voice/query",
  "v1/voice/query/stream",
  "v1/strategies",
  "v1/bench",
  "v1/documents/ingest",
];

const USER_DOCUMENT_PATH = /^v1\/documents\/user-[a-f0-9]+$/;

function isAllowedPath(target: string): boolean {
  return ALLOWED_PREFIXES.includes(target) || USER_DOCUMENT_PATH.test(target);
}

async function proxy(request: NextRequest, path: string[]): Promise<Response> {
  const target = path.join("/");
  if (!isAllowedPath(target)) {
    return Response.json({ detail: `unsupported path: ${target}` }, { status: 404 });
  }
  if (!API_TOKEN) {
    return Response.json(
      { detail: "FASTRAG_QUERY_TOKEN is not configured on the server" },
      { status: 500 },
    );
  }

  if (target === "v1/documents/ingest") {
    const contentType = request.headers.get("content-type") ?? "";
    if (!contentType.toLowerCase().includes("multipart/form-data")) {
      return Response.json({ detail: "document ingest requires multipart/form-data" }, { status: 415 });
    }
    const contentLength = request.headers.get("content-length");
    if (contentLength) {
      const bytes = Number.parseInt(contentLength, 10);
      if (Number.isFinite(bytes) && bytes > MAX_UPLOAD_BYTES) {
        return Response.json(
          { detail: `document exceeds ${MAX_UPLOAD_BYTES} bytes` },
          { status: 413 },
        );
      }
    }
  }

  const headers = new Headers();
  headers.set("Authorization", `Bearer ${API_TOKEN}`);
  const contentType = request.headers.get("content-type");
  // Multipart uploads carry a generated boundary, so the header must pass through
  // untouched or the backend cannot parse the body.
  if (contentType) headers.set("content-type", contentType);

  const init: RequestInit & { duplex?: "half" } = {
    method: request.method,
    headers,
  };
  if (request.method !== "GET") {
    init.body = request.body;
    init.duplex = "half";
  }

  let upstream: Response;
  try {
    upstream = await fetch(`${API_URL.replace(/\/$/, "")}/${target}`, init);
  } catch (error) {
    return Response.json(
      { detail: `cannot reach the FastRAG API at ${API_URL}`, error: String(error) },
      { status: 502 },
    );
  }

  const responseHeaders = new Headers();
  const upstreamType = upstream.headers.get("content-type");
  if (upstreamType) responseHeaders.set("content-type", upstreamType);
  if (upstreamType?.includes("event-stream")) {
    responseHeaders.set("cache-control", "no-cache, no-transform");
    responseHeaders.set("connection", "keep-alive");
  }

  return new Response(upstream.body, {
    status: upstream.status,
    headers: responseHeaders,
  });
}

export async function GET(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  return proxy(request, (await context.params).path);
}

export async function POST(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  return proxy(request, (await context.params).path);
}

export async function DELETE(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  return proxy(request, (await context.params).path);
}
