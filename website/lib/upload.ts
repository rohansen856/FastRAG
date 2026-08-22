/** Keep in sync with `src/fastrag/documents.py` (10 MiB, supported suffixes). */

export const MAX_UPLOAD_BYTES = 10 * 1024 * 1024;
export const MAX_ATTACHMENTS = 5;

export const SUPPORTED_EXTENSIONS = [
  ".pdf",
  ".md",
  ".markdown",
  ".txt",
  ".html",
  ".htm",
  ".json",
  ".jsonl",
  ".csv",
  ".tsv",
  ".xml",
  ".yaml",
  ".yml",
  ".rst",
  ".log",
] as const;

export const UPLOAD_ACCEPT = SUPPORTED_EXTENSIONS.join(",");

const ALLOWED = new Set<string>(SUPPORTED_EXTENSIONS);

export function fileExtension(name: string): string {
  const dot = name.lastIndexOf(".");
  return dot === -1 ? "" : name.slice(dot).toLowerCase();
}

export function validateUploadFile(file: File): string | null {
  if (file.size === 0) {
    return "That file is empty. Choose a document with text content.";
  }
  if (file.size > MAX_UPLOAD_BYTES) {
    const maxMiB = MAX_UPLOAD_BYTES / (1024 * 1024);
    return `File is too large (${(file.size / (1024 * 1024)).toFixed(1)} MiB). Maximum is ${maxMiB} MiB.`;
  }
  const ext = fileExtension(file.name);
  if (!ext || !ALLOWED.has(ext)) {
    return "Unsupported file type. Use PDF, Markdown, text, HTML, JSON, CSV, XML, YAML, or similar.";
  }
  return null;
}
