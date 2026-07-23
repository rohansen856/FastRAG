"""Script-aware text utilities.

The corpus spans Latin and Indic scripts, so sentence segmentation cannot assume
`.!?`. Devanagari, Bengali, Marathi and Sanskrit terminate sentences with the
danda (U+0964); Urdu uses the Arabic full stop (U+06D4). Missing these does not
just chunk badly, it stalls streaming: the citation buffer would hold an entire
Hindi answer until the stream closed.
"""

from __future__ import annotations

import re
import unicodedata

# Danda, double danda, Arabic full stop, Arabic question mark, and fullwidth stops.
SENTENCE_TERMINATORS = ".!?\u0964\u0965\u06d4\u061f\u3002\uff01\uff1f"
SENTENCE_END_RE = re.compile(rf"(?<=[{re.escape(SENTENCE_TERMINATORS)}])(?:\s+|$)|\n+")

_SCRIPT_RANGES: tuple[tuple[int, int, str], ...] = (
    (0x0900, 0x097F, "hi"),  # Devanagari - Hindi, Marathi, Sanskrit, Nepali
    (0x0980, 0x09FF, "bn"),  # Bengali, Assamese
    (0x0A00, 0x0A7F, "pa"),  # Gurmukhi
    (0x0A80, 0x0AFF, "gu"),  # Gujarati
    (0x0B00, 0x0B7F, "or"),  # Odia
    (0x0B80, 0x0BFF, "ta"),  # Tamil
    (0x0C00, 0x0C7F, "te"),  # Telugu
    (0x0C80, 0x0CFF, "kn"),  # Kannada
    (0x0D00, 0x0D7F, "ml"),  # Malayalam
    (0x0600, 0x06FF, "ur"),  # Arabic - Urdu
)


def split_sentences(text: str) -> list[str]:
    return [part.strip() for part in SENTENCE_END_RE.split(text) if part and part.strip()]


def detect_script_language(text: str) -> str:
    """Best-effort language code from the dominant script.

    Devanagari is shared by Hindi, Marathi, Sanskrit and Nepali, so this cannot
    distinguish them; it only answers "which script family", which is what the
    language guardrail needs.
    """
    counts: dict[str, int] = {}
    for character in text:
        if not character.isalpha():
            continue
        code = ord(character)
        for start, end, language in _SCRIPT_RANGES:
            if start <= code <= end:
                counts[language] = counts.get(language, 0) + 1
                break
        else:
            if code < 0x0250:
                counts["en"] = counts.get("en", 0) + 1
    if not counts:
        return "unknown"
    return max(counts.items(), key=lambda item: item[1])[0]


def normalize_text(text: str) -> str:
    """NFC-normalise and collapse whitespace.

    Indic text round-tripped through translation pipelines arrives in mixed
    normalisation forms; without this, identical strings hash differently and
    silently miss the exact cache.
    """
    return " ".join(unicodedata.normalize("NFC", text).split())
