"""Turn repository files into `SourceDocument`s, split by structure.

One document per *file* is too coarse: `pipeline.py` is 787 lines, and a chunk
drawn from the middle of it answers nothing cleanly. Markdown is split per `##`
section and Python per top-level `def`/`class`, so every document is about one
thing and a golden question can be grounded to it mechanically.
"""

from __future__ import annotations

import ast
import hashlib
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from fastrag.chunking import SourceDocument

# Files whose content becomes the corpus. Frontend TypeScript is deliberately
# absent: 57 of its files are vendored shadcn primitives, and the boilerplate
# JSX dilutes retrieval without answering questions anyone asks.
INCLUDE_GLOBS: tuple[str, ...] = (
    "docs/*.md",
    "README.md",
    "AGENTS.md",
    "src/fastrag/*.py",
    "src/fastrag/adapters/*.py",
    "scripts/*.py",
    "compose.yaml",
    "render.yaml",
    "pyproject.toml",
    ".env.local.example",
    ".env.cloud.example",
)

# Held out of the index so questions derived from them are genuinely
# unanswerable. See `scripts/selfcorpus/golden.py` for why this list is small:
# an exclusion only yields a usable negative when nothing *included* covers the
# same ground, and this repository documents itself twice over.
HELD_OUT_GLOBS: tuple[str, ...] = (
    "web/app/*.tsx",
    "web/components/*.tsx",
    "website/lib/*.ts",
)

PROSE_SUFFIXES = frozenset({".md"})
CODE_SUFFIXES = frozenset({".py"})

GITHUB_URL = "https://github.com/rohansen856/FastRAG"

# docs/<file>.md renders on the marketing site at /docs/<slug>. The slug is the
# filename minus the suffix except for this one rename; mirrors DOC_SECTIONS in
# website/lib/docs.ts. Files absent from the site fall back to a GitHub blob URL.
DOC_SLUG_OVERRIDES: dict[str, str] = {"local-setup.md": "running-locally"}
DOC_SLUGS: frozenset[str] = frozenset(
    {
        "local-setup.md",
        "deployment.md",
        "providers.md",
        "architecture.md",
        "self-corpus.md",
        "chunking.md",
        "crag.md",
        "guardrails.md",
        "voice.md",
        "latency.md",
        "operations.md",
        "runbook.md",
        "benchmarking.md",
        "llm-providers.md",
    }
)

_HEADING_RE = re.compile(r"^##\s+(.*)$", re.MULTILINE)


@dataclass(frozen=True, slots=True)
class RepoFile:
    path: str          # repo-relative, e.g. "src/fastrag/crag.py"
    text: str
    category: str      # documentation | source | configuration


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def git_commit(root: Path) -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def _git_ls_files(root: Path, globs: tuple[str, ...]) -> list[str]:
    """List tracked files matching `globs`.

    Going through git rather than `Path.glob` means the corpus never picks up
    build output, virtualenvs or anything else `.gitignore` excludes, and the
    same command produces the same corpus on any machine.
    """
    result = subprocess.run(
        ["git", "ls-files", "--", *globs],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    )
    return sorted(line for line in result.stdout.splitlines() if line.strip())


def _category(path: str) -> str:
    suffix = Path(path).suffix.casefold()
    if suffix in PROSE_SUFFIXES:
        return "documentation"
    if suffix in CODE_SUFFIXES:
        return "source"
    return "configuration"


def load_repo_files(root: Path, globs: tuple[str, ...] = INCLUDE_GLOBS) -> list[RepoFile]:
    files: list[RepoFile] = []
    for path in _git_ls_files(root, globs):
        text = (root / path).read_text(encoding="utf-8", errors="replace")
        if not text.strip():
            continue
        files.append(RepoFile(path=path, text=text, category=_category(path)))
    return files


def document_key(path: str, symbol: str) -> str:
    """Language-independent identity for a section.

    A document and its translations describe the same thing, so they share a key
    even though they have different ids. That is what lets a question written
    from the English text be relabelled against the Hindi chunks, and what keeps
    a section and its translations on the same side of the golden/calibration
    split.
    """
    return f"{path}:{symbol}"


def document_id(path: str, symbol: str, language: str) -> str:
    """Stable id for one section of one file in one language.

    Hashes the *repo-relative* path. `IndexBuilder._load_documents` hashes the
    resolved absolute path, which differs between a laptop and CI and would make
    every golden `relevant_chunk_id` non-portable.

    The language is part of the id because a document and its translations are
    different documents. Sharing an id across languages would let a lookup keyed
    on `document_id` hand an English question the Hindi translation's chunks.
    """
    return hashlib.sha256(f"self:{language}:{path}:{symbol}".encode()).hexdigest()[:24]


def source_uri(
    path: str,
    commit: str,
    start: int | None = None,
    end: int | None = None,
    *,
    site_url: str | None = None,
) -> str:
    """An absolute `https://` URL, so citations render as links.

    `CitationLink` in the website only builds an anchor for `^https?://`, which
    is why the MS MARCO corpus's `msmarco-xi://` URIs rendered as inert text. A
    relative `/docs/...` would not linkify either, so documentation only points
    at the site when a base URL is configured; otherwise everything falls back
    to a GitHub blob URL pinned to the ingested commit, which keeps a citation
    pointing at the code that was actually indexed.
    """
    name = Path(path).name
    if site_url and path.startswith("docs/") and name in DOC_SLUGS:
        slug = DOC_SLUG_OVERRIDES.get(name, name.removesuffix(".md"))
        return f"{site_url.rstrip('/')}/docs/{slug}"
    anchor = ""
    if start is not None:
        anchor = f"#L{start}" + (f"-L{end}" if end and end != start else "")
    return f"{GITHUB_URL}/blob/{commit}/{path}{anchor}"


def _markdown_sections(file: RepoFile) -> list[tuple[str, str]]:
    """Split on `##` headings, keeping the preamble under the document title."""
    matches = list(_HEADING_RE.finditer(file.text))
    if not matches:
        return [("", file.text)]
    sections: list[tuple[str, str]] = []
    preamble = file.text[: matches[0].start()].strip()
    if preamble:
        sections.append(("", preamble))
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(file.text)
        body = file.text[match.start() : end].strip()
        if body:
            sections.append((match.group(1).strip(), body))
    return sections


def _python_sections(file: RepoFile) -> list[tuple[str, str, int, int]]:
    """One section per top-level def/class, plus a module header.

    Splitting on the AST rather than letting the sentence chunker loose on raw
    source matters: `SENTENCE_END_RE` treats both newlines and `.` + whitespace
    as sentence ends, and `self._registry.activate(...)` is full of both, so
    packed chunks would otherwise straddle unrelated functions.
    """
    try:
        tree = ast.parse(file.text)
    except SyntaxError:
        return [("", file.text, 1, len(file.text.splitlines()))]

    lines = file.text.splitlines()
    sections: list[tuple[str, str, int, int]] = []
    top_level = ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef
    body = [node for node in tree.body if isinstance(node, top_level)]

    first = min((node.lineno for node in body), default=len(lines) + 1)
    header = "\n".join(lines[: first - 1]).strip()
    if header:
        # Module docstring, imports and constants: where a file explains itself.
        sections.append(("module header", header, 1, first - 1))

    for node in body:
        start, end = node.lineno, (node.end_lineno or node.lineno)
        segment = ast.get_source_segment(file.text, node) or "\n".join(lines[start - 1 : end])
        if segment.strip():
            sections.append((node.name, segment, start, end))
    return sections


def build_documents(
    files: list[RepoFile],
    commit: str,
    *,
    language: str = "en",
    site_url: str | None = None,
) -> list[SourceDocument]:
    """Split every file into section-sized documents ready for chunking."""
    documents: list[SourceDocument] = []
    for file in files:
        suffix = Path(file.path).suffix.casefold()
        if suffix in PROSE_SUFFIXES:
            entries = [
                (heading, body, None, None) for heading, body in _markdown_sections(file)
            ]
        elif suffix in CODE_SUFFIXES:
            entries = [
                (symbol, body, start, end) for symbol, body, start, end in _python_sections(file)
            ]
        else:
            entries = [("", file.text, None, None)]

        for symbol, body, start, end in entries:
            title = f"{file.path} — {symbol}" if symbol else file.path
            documents.append(
                SourceDocument(
                    document_id=document_id(file.path, symbol, language),
                    text=body,
                    title=title,
                    source_uri=source_uri(file.path, commit, start, end, site_url=site_url),
                    # Explicit, never detected: a translated doc that keeps its
                    # Latin-script code fences and env-var names would be
                    # miscounted as English by `detect_script_language`.
                    language=language,
                    metadata={
                        "section": symbol or Path(file.path).stem,
                        "category": file.category,
                        "repo_path": file.path,
                        "document_key": document_key(file.path, symbol),
                    },
                )
            )
    return documents


def translated_document(
    document: SourceDocument, language: str, text: str
) -> SourceDocument:
    """Clone a document into another language, keeping its identity.

    The `document_key` stays the English one deliberately. Translating a Markdown
    `##` heading changes the section title, so keying on the translated text
    would give the translation a different key from its original and no Indic
    golden item could ever be matched to its chunks.
    """
    metadata = dict(document.metadata)
    metadata["translated_from"] = document.language or "en"
    return SourceDocument(
        document_id=document_id(
            str(metadata.get("repo_path", "")), str(metadata.get("section", "")), language
        ),
        text=text,
        title=document.title,
        source_uri=document.source_uri,
        page=document.page,
        language=language,
        metadata=metadata,
    )
