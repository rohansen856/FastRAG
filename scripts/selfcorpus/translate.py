"""Machine-translate the prose docs so the corpus stays genuinely multilingual.

The `language` payload filter, the six-language golden split and
`FASTRAG_GUARDRAIL_LANGUAGES` all assume chunks actually exist in each language.
An English-only self-corpus would leave `language=hi` matching zero points, so
the documentation is translated the same way MSMARCO-XI is itself a machine
translation of MS MARCO.

Only prose is translated. Source code is not: a translated identifier answers
nothing, and `detect_script_language` would read it as English anyway.
"""

from __future__ import annotations

import asyncio
import hashlib
import re
from pathlib import Path
from typing import Any

LANGUAGE_NAMES: dict[str, str] = {
    "hi": "Hindi",
    "bn": "Bengali",
    "ta": "Tamil",
    "te": "Telugu",
    "mr": "Marathi",
}

TRANSLATE_SYSTEM = (
    "You translate technical documentation. Translate the prose faithfully into "
    "{language}. Leave every code block, inline code span, identifier, file path, "
    "URL, environment variable and command-line flag exactly as written in the "
    "source, including inside headings. Preserve Markdown structure. Return JSON "
    "matching the schema and nothing else."
)

TRANSLATE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {"translation": {"type": "string"}},
    "required": ["translation"],
    "additionalProperties": False,
}

# Sections of one file are translated in a single call. Per-section calls put the
# run well past a free-tier daily request quota - 116 sections across five
# languages is 580 requests on its own - and the sections of one file share
# context anyway, which makes the translation more consistent, not less.
BATCH_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "translations": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["translations"],
    "additionalProperties": False,
}

BATCH_SYSTEM = (
    "You translate technical documentation into {language}. You are given "
    "numbered sections. Return a JSON array with exactly one translation per "
    "section, in the same order. Translate the prose faithfully. Leave every code "
    "block, inline code span, identifier, file path, URL, environment variable and "
    "command-line flag exactly as written in the source, including inside headings. "
    "Preserve Markdown structure."
)

# Long documents are translated a section at a time: a whole file overruns the
# generator's output budget and silently returns a truncated translation.
MAX_SECTION_WORDS = 600

# Providers meter tokens per minute, and the quota covers the prompt *and* the
# reserved completion: a free Groq tier allows 8000, so asking for a fixed
# `max_tokens=8000` alongside any real input is rejected outright rather than
# queued. Batches are therefore sized by estimated tokens, not by section count.
CHARS_PER_TOKEN = 4
# How much prompt one batch may carry. Kept well under the per-minute quota so
# the reserved completion below still fits beside it.
INPUT_BUDGET = 700
# Devanagari, Bengali and Tamil tokenize far worse than the English they are
# translated from - commonly three to five tokens where English needs one. Under
# -reserving does not truncate politely: the model stops mid-object and the
# provider rejects the whole call as `json_validate_failed`, wasting every token
# it just spent. Tamil and Telugu are the worst of them, so this errs high;
# over-reserving only costs quota, and a rejected call costs all of it.
OUTPUT_RATIO = 6.0
TOKEN_BUDGET = int(INPUT_BUDGET * (1 + OUTPUT_RATIO))


def cache_path(root: Path, language: str, key: str) -> Path:
    """One cached file per document, named after its key rather than its file.

    Documents are sections, so a file yields many; caching per section keeps a
    partial run's work and makes each translation reviewable on its own.
    """
    safe = hashlib.sha1(key.encode()).hexdigest()[:16]
    stem = key.split(":")[0].replace("/", "__")
    return root / "eval" / "translations" / language / f"{stem}.{safe}.md"


async def translate_text(
    generator: Any, text: str, language: str, *, max_tokens: int = 3000
) -> str:
    result = await generator.complete_json(
        system=TRANSLATE_SYSTEM.format(language=LANGUAGE_NAMES[language]),
        user=text,
        schema=TRANSLATE_SCHEMA,
        schema_name="translation",
        max_tokens=max_tokens,
    )
    translated = str(result.get("translation") or "").strip()
    if not translated:
        raise RuntimeError(f"empty {language} translation")
    return translated


def _split_for_translation(text: str, max_words: int = MAX_SECTION_WORDS) -> list[str]:
    paragraphs = text.split("\n\n")
    blocks: list[str] = []
    current: list[str] = []
    count = 0
    for paragraph in paragraphs:
        words = len(paragraph.split())
        if current and count + words > max_words:
            blocks.append("\n\n".join(current))
            current, count = [], 0
        current.append(paragraph)
        count += words
    if current:
        blocks.append("\n\n".join(current))
    return blocks or [text]


_SECTION_MARKER_RE = re.compile(r"^\s*#{0,6}\s*SECTION\s+\d+\s*", re.IGNORECASE)


def clean_translation(text: str) -> str:
    """Undo two things models reliably do to a batched translation.

    They echo the `### SECTION n` marker that numbered the input, and they emit
    the literal two characters backslash-n inside the JSON string instead of a
    newline. Left alone, the first pollutes every chunk with a marker the reader
    never asked about and the second collapses a Markdown section into one line,
    which defeats sentence splitting and the citation excerpt with it.
    """
    cleaned = text.replace("\\r\\n", "\n").replace("\\n", "\n").replace("\\t", "\t")
    return _SECTION_MARKER_RE.sub("", cleaned, count=1).strip()


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // CHARS_PER_TOKEN)


def plan_batches(
    documents: list[Any], *, budget: int = INPUT_BUDGET, max_items: int = 6
) -> list[list[Any]]:
    """Group documents so the prompt stays inside `budget` input tokens.

    The reserved completion is sized from the same estimate in `translate_batch`,
    so prompt and reservation together stay under the per-minute quota.

    A section that cannot fit even alone still gets its own batch: it will be
    rejected loudly by the provider rather than silently dropped here.
    """
    batches: list[list[Any]] = []
    current: list[Any] = []
    total = 0
    for document in documents:
        cost = estimate_tokens(document.text)
        if current and (total + cost > budget or len(current) >= max_items):
            batches.append(current)
            current, total = [], 0
        current.append(document)
        total += cost
    if current:
        batches.append(current)
    return batches


async def translate_batch(
    generator: Any, texts: list[str], language: str, *, max_tokens: int | None = None
) -> list[str]:
    """Translate several sections in one call, or raise if the shapes disagree.

    The count check is the whole safety of batching: a model that drops or merges
    a section would otherwise shift every translation onto the wrong document.
    """
    numbered = "\n\n".join(
        f"### SECTION {index}\n{text}" for index, text in enumerate(texts)
    )
    if max_tokens is None:
        # Reserve only what the output plausibly needs; an over-reservation is
        # charged against the per-minute quota exactly like real output.
        max_tokens = int(estimate_tokens(numbered) * OUTPUT_RATIO) + 256
    result = await generator.complete_json(
        system=BATCH_SYSTEM.format(language=LANGUAGE_NAMES[language]),
        user=numbered,
        schema=BATCH_SCHEMA,
        schema_name="translations",
        max_tokens=max_tokens,
    )
    translations = result.get("translations")
    if not isinstance(translations, list) or len(translations) != len(texts):
        got = len(translations) if isinstance(translations, list) else "none"
        raise RuntimeError(f"expected {len(texts)} {language} translations, got {got}")
    cleaned = [clean_translation(str(item)) for item in translations]
    if not all(cleaned):
        raise RuntimeError(f"empty section in {language} translation")
    return cleaned


async def translate_documents(
    generator: Any,
    documents: list[Any],
    *,
    root: Path,
    languages: list[str],
    refresh: bool = False,
    concurrency: int = 1,
    batch_size: int = 6,
    on_error: Any = None,
) -> list[Any]:
    """Translate each prose document, returning new documents in each language.

    Translation happens per *document*, not per file, so a translated section
    keeps the identity of the English section it came from. Translating a whole
    file and re-splitting it would key sections on their translated headings, and
    no Indic golden item could then be matched to its chunks.

    Calls are batched by file to stay inside a free-tier request quota, and every
    result is cached per section so a partial run keeps its work.
    """
    from . import sources

    semaphore = asyncio.Semaphore(concurrency)
    results: list[Any] = []

    def cached(document: Any, language: str) -> Any | None:
        destination = cache_path(root, language, str(document.metadata["document_key"]))
        if destination.is_file() and not refresh:
            text = destination.read_text(encoding="utf-8")
            return sources.translated_document(document, language, text)
        return None

    def store(document: Any, language: str, text: str) -> Any:
        destination = cache_path(root, language, str(document.metadata["document_key"]))
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(text, encoding="utf-8")
        return sources.translated_document(document, language, text)

    async def attempt(batch: list[Any], language: str) -> Exception | None:
        """One provider call, holding the semaphore only for its duration."""
        async with semaphore:
            try:
                translations = await translate_batch(
                    generator, [document.text for document in batch], language
                )
            except Exception as exc:  # noqa: BLE001 - returned, not swallowed
                return exc
        for document, text in zip(batch, translations, strict=True):
            results.append(store(document, language, text))
        return None

    async def run_batch(batch: list[Any], language: str) -> None:
        failure = await attempt(batch, language)
        if failure is None:
            return
        if len(batch) > 1:
            # A batch is rejected as a unit, and the usual cause is one section
            # whose output overran the reservation. Retrying the members singly
            # rescues the rest instead of losing the whole batch to one of them,
            # and each then gets a reservation sized for it alone. The retry sits
            # outside `attempt` so it never waits on a semaphore its own caller
            # is still holding - doing that inside deadlocks at concurrency 1.
            for document in batch:
                await run_batch([document], language)
            return
        if on_error is not None:
            on_error(str(batch[0].metadata["document_key"]), language, failure)

    tasks = []
    for language in languages:
        pending: list[Any] = []
        for document in documents:
            hit = cached(document, language)
            if hit is not None:
                results.append(hit)
                continue
            pending.append(document)
        for batch in plan_batches(pending, max_items=batch_size):
            tasks.append(run_batch(batch, language))
    await asyncio.gather(*tasks)
    return results
