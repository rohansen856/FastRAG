import { readFileSync } from "fs";
import { join } from "path";

export function docsRoot(): string {
  return join(process.cwd(), "..", "docs");
}

export function loadDocMarkdown(filename: string): string {
  return readFileSync(join(docsRoot(), filename), "utf-8");
}
