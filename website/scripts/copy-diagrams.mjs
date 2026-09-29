// Copy the rendered architecture diagrams from docs/diagrams into public/diagrams so the
// site serves them at /diagrams/<folder>/<name>.html. Only the self-contained .html files
// are copied; candidate.json sources and local finalize evidence stay in docs/.
import { cpSync, existsSync, mkdirSync, readdirSync, rmSync, statSync } from "node:fs";
import { dirname, join, relative } from "node:path";
import { fileURLToPath } from "node:url";

const websiteRoot = join(dirname(fileURLToPath(import.meta.url)), "..");
const source = join(websiteRoot, "..", "docs", "diagrams");
const target = join(websiteRoot, "public", "diagrams");

function htmlFiles(dir) {
  return readdirSync(dir).flatMap((name) => {
    if (name.startsWith(".")) return [];
    const path = join(dir, name);
    if (statSync(path).isDirectory()) return htmlFiles(path);
    return name.endsWith(".html") ? [path] : [];
  });
}

rmSync(target, { recursive: true, force: true });
if (!existsSync(source)) {
  console.warn(`copy-diagrams: ${source} not found; /diagrams will be empty`);
  process.exit(0);
}

const files = htmlFiles(source);
for (const file of files) {
  const destination = join(target, relative(source, file));
  mkdirSync(dirname(destination), { recursive: true });
  cpSync(file, destination);
}
console.log(`copy-diagrams: ${files.length} diagrams → public/diagrams`);
