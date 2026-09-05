"""Tests for the self-corpus ingest path and the corpus-safety checks it relies on."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from fastrag.calibration import Calibration, CalibrationError
from fastrag.chunking import SourceDocument, build_strategy, chunk_document, display_text_of
from fastrag.domain import Chunk
from fastrag.text import normalize_language

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from selfcorpus import golden as golden_mod  # noqa: E402
from selfcorpus import sources  # noqa: E402

CODE = '''def handler(value: int) -> int:
    """Double it."""
    if value < 0:
        return 0
    return value * 2
'''


def _document(text: str = CODE) -> SourceDocument:
    return SourceDocument(
        document_id="doc-1",
        text=text,
        title="src/fastrag/thing.py — handler",
        source_uri="https://example.invalid/blob/abc/thing.py#L1-L5",
        language="en",
        metadata={"section": "handler", "category": "source"},
    )


def _chunk(payload: dict[str, object]) -> Chunk:
    return Chunk(
        chunk_id=str(payload["chunk_id"]),
        document_id=str(payload["document_id"]),
        text=str(payload["text"]),
        title=str(payload["title"]),
        source_uri=str(payload["source_uri"]),
        page=None,
        score=1.0,
        metadata=dict(payload),
    )


@pytest.mark.asyncio
async def test_whole_document_chunk_keeps_verbatim_layout() -> None:
    """Code cited back to the user must keep its indentation.

    `normalize_text` collapses every whitespace run, which is right for
    embedding and cache stability and useless for reading Python.
    """
    strategy = build_strategy("sentence", chunk_size=400, chunk_overlap=50)
    payloads = await chunk_document(_document(), [strategy])
    assert len(payloads) == 1
    chunk = _chunk(payloads[0])
    assert "\n    return value * 2" in display_text_of(chunk)
    # The embedded and cited text stays normalised.
    assert "\n" not in str(payloads[0]["text"])


@pytest.mark.asyncio
async def test_display_text_falls_back_without_raw_text() -> None:
    chunk = Chunk(
        chunk_id="c1",
        document_id="d1",
        text="collapsed text",
        title="t",
        source_uri="",
        page=None,
        score=1.0,
        metadata={},
    )
    assert display_text_of(chunk) == "collapsed text"


@pytest.mark.asyncio
async def test_raw_text_does_not_change_chunk_ids() -> None:
    """The id hashes the normalised text, so adding a payload field is a no-op for it."""
    strategy = build_strategy("sentence", chunk_size=400, chunk_overlap=50)
    payloads = await chunk_document(_document(), [strategy])
    import uuid

    expected = str(
        uuid.uuid5(uuid.NAMESPACE_URL, f"doc-1:sentence:{payloads[0]['text']}")
    )
    assert payloads[0]["chunk_id"] == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [("hi-IN", "hi"), ("bn_IN", "bn"), ("EN", "en"), ("ta", "ta"), ("", None), (None, None)],
)
def test_normalize_language(value: str | None, expected: str | None) -> None:
    """The UIs send BCP-47; chunk payloads hold ISO 639-1 and are matched exactly."""
    assert normalize_language(value) == expected


def _calibration(content_version: str | None) -> Calibration:
    return Calibration(
        reranker_threshold=0.5,
        reranker_fingerprint="r",
        embedding_fingerprint="e",
        false_answer_rate=0.0,
        sample_count=30,
        content_version=content_version,
    )


def test_validate_corpus_rejects_a_different_corpus() -> None:
    with pytest.raises(CalibrationError, match="recalibrate"):
        _calibration("msmarco-digest").validate_corpus("self-corpus-digest")


def test_validate_corpus_accepts_matching_and_absent() -> None:
    _calibration("same").validate_corpus("same")
    # Artifacts predating the field still load rather than blocking startup.
    _calibration(None).validate_corpus("anything")


def test_split_pool_is_disjoint_by_document() -> None:
    """Two questions from one section are near-duplicates; they must not straddle the split."""
    candidates = [
        golden_mod.GoldenCandidate(
            id=f"self-en-{index}",
            query=f"q{index}",
            reference_answer="a",
            answerable=True,
            relevant_chunk_ids=["c"],
            category="source",
            language="en",
            document_key=f"doc-{index % 25}",
            )
        for index in range(200)
    ]
    golden, calibration = golden_mod.split_pool(candidates)
    assert golden and calibration
    assert not ({item.id for item in golden} & {item.id for item in calibration})
    assert not (
        {item.document_key for item in golden} & {item.document_key for item in calibration}
    )


def test_source_uri_is_absolute_so_citations_linkify() -> None:
    """CitationLink only builds an anchor for ^https?://; a relative path renders as text."""
    blob = sources.source_uri("src/fastrag/crag.py", "abc123", 10, 20)
    assert blob.startswith("https://") and blob.endswith("crag.py#L10-L20")
    assert sources.source_uri("docs/crag.md", "abc").startswith("https://")
    site = sources.source_uri("docs/local-setup.md", "abc", site_url="https://fastrag.dev")
    assert site == "https://fastrag.dev/docs/running-locally"


def test_chunk_ids_by_document_ignores_other_strategies() -> None:
    """Labels are strategy-specific; evaluation retrieves with chunk_strategy_list[0]."""
    chunks = [
        {"document_id": "en1", "chunk_id": "a", "strategy": "sentence", "language": "en"},
        {"document_id": "en1", "chunk_id": "b", "strategy": "sentence_window", "language": "en"},
    ]
    keys = {"en1": "thing.py:handler"}
    index = golden_mod.chunk_ids_by_document(chunks, "sentence", keys, language="en")
    assert index == {"thing.py:handler": ["a"]}


def test_chunk_ids_by_document_separates_translations() -> None:
    """A document and its translation share a key but must not share chunk ids.

    They have different `document_id`s precisely so an English question cannot be
    relabelled onto Hindi chunks by accident; the language filter is what picks
    which translation a question is scored against.
    """
    key = "docs/crag.md:Three bands"
    chunks = [
        {"document_id": "en1", "chunk_id": "a", "strategy": "sentence", "language": "en"},
        {"document_id": "hi1", "chunk_id": "b", "strategy": "sentence", "language": "hi"},
    ]
    keys = {"en1": key, "hi1": key}
    assert golden_mod.chunk_ids_by_document(chunks, "sentence", keys, language="en") == {key: ["a"]}
    assert golden_mod.chunk_ids_by_document(chunks, "sentence", keys, language="hi") == {key: ["b"]}


def test_document_id_is_language_scoped_but_key_is_not() -> None:
    assert sources.document_key("a.py", "f") == sources.document_key("a.py", "f")
    assert sources.document_id("a.py", "f", "en") != sources.document_id("a.py", "f", "hi")


def _load_ingest_module() -> object:
    """`scripts/ingest-self.py` is not importable by name (hyphen), so load by path."""
    import importlib.util

    path = Path(__file__).resolve().parents[1] / "scripts" / "ingest-self.py"
    spec = importlib.util.spec_from_file_location("ingest_self", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_assert_labels_indexed_catches_drift() -> None:
    """A label naming a chunk that was never indexed must fail loudly here.

    Otherwise recall@20 silently collapses to zero three commands later and the
    failure reads like a retrieval regression rather than a stale label.
    """
    module = _load_ingest_module()
    chunks = [{"chunk_id": "present"}]
    module.assert_labels_indexed([{"relevant_chunk_ids": ["present"]}], chunks)
    with pytest.raises(SystemExit, match="out of sync"):
        module.assert_labels_indexed([{"relevant_chunk_ids": ["missing"]}], chunks)


def test_check_minimums_names_every_downstream_bound() -> None:
    module = _load_ingest_module()
    golden = [{"id": f"g{i}", "answerable": i % 2 == 0} for i in range(200)]
    calibration = [{"id": f"c{i}", "answerable": False} for i in range(40)]
    pairs = [{"left": "a", "right": "b", "equivalent": True}] * 30
    module.check_minimums(golden, calibration, pairs)

    with pytest.raises(SystemExit) as excinfo:
        module.check_minimums(golden[:10], calibration[:5], pairs[:2])
    message = str(excinfo.value)
    assert "load_golden requires 200" in message
    assert "calibrate requires 30" in message
    assert "cache pairs" in message


class _StubGenerator:
    """Returns a Markdown section whose heading differs from the English one."""

    async def complete_json(self, *, system, user, schema, schema_name, **_: object):
        if "translations" in schema["properties"]:
            count = user.count("### SECTION ")
            return {"translations": ["## अनुवादित शीर्षक\nहिन्दी पाठ यहाँ है।"] * count}
        return {"questions": ["अनुवादित प्रश्न"]}


@pytest.mark.asyncio
async def test_translation_keeps_the_english_document_key(tmp_path: Path) -> None:
    """A translated section must stay matchable to the English one it came from.

    Translating a Markdown `##` heading changes the section title, so building
    translated documents by re-splitting a translated file would key them on the
    translated heading and no Indic golden item could find its chunks.
    """
    from selfcorpus import translate

    english = SourceDocument(
        document_id=sources.document_id("docs/crag.md", "Three bands", "en"),
        text="## Three bands\nEnglish body text.",
        title="docs/crag.md — Three bands",
        source_uri="https://example.invalid/docs/crag",
        language="en",
        metadata={
            "section": "Three bands",
            "category": "documentation",
            "repo_path": "docs/crag.md",
            "document_key": sources.document_key("docs/crag.md", "Three bands"),
        },
    )
    translated = await translate.translate_documents(
        _StubGenerator(), [english], root=tmp_path, languages=["hi"]
    )
    assert len(translated) == 1
    hindi = translated[0]
    assert hindi.metadata["document_key"] == english.metadata["document_key"]
    assert hindi.language == "hi"
    # Different ids, so their chunks never collide or deduplicate into each other.
    assert hindi.document_id != english.document_id


def _cached_files(root: Path) -> list[Path]:
    return list(root.rglob("*.md"))


class _MiscountingGenerator:
    """Returns fewer translations than sections, as a sloppy model would."""

    async def complete_json(self, *, system, user, schema, schema_name, **_: object):
        return {"translations": ["only one"]}


@pytest.mark.asyncio
async def test_batched_translation_rejects_a_count_mismatch(tmp_path: Path) -> None:
    """A dropped section would shift every translation onto the wrong document.

    Batching is only safe because the count is checked, so a short array must
    discard the batch rather than zip what it got onto the first few documents.
    """
    from selfcorpus import translate

    documents = [
        SourceDocument(
            document_id=sources.document_id("docs/a.md", f"S{index}", "en"),
            text=f"## S{index}\nbody {index}",
            title=f"docs/a.md — S{index}",
            source_uri="https://example.invalid",
            language="en",
            metadata={
                "section": f"S{index}",
                "category": "documentation",
                "repo_path": "docs/a.md",
                "document_key": sources.document_key("docs/a.md", f"S{index}"),
            },
        )
        for index in range(3)
    ]
    errors: list[str] = []
    result = await translate.translate_documents(
        _MiscountingGenerator(),
        documents,
        root=tmp_path,
        languages=["hi"],
        on_error=lambda key, language, exc: errors.append(f"{language}:{key}"),
    )
    assert result == []
    assert len(errors) == 3
    # Nothing cached, so a re-run retries rather than persisting a bad batch.
    assert not _cached_files(tmp_path)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        # The marker that numbered the input, echoed back into the translation.
        ("### SECTION 3\n## शीर्षक", "## शीर्षक"),
        ("SECTION 0 body", "body"),
        # Literal backslash-n, which would collapse a section into one line and
        # defeat both sentence splitting and the citation excerpt.
        ("line one\\nline two", "line one\nline two"),
        ("## Real heading\nuntouched", "## Real heading\nuntouched"),
    ],
)
def test_clean_translation(raw: str, expected: str) -> None:
    from selfcorpus.translate import clean_translation

    assert clean_translation(raw) == expected


def test_plan_batches_respects_the_token_budget() -> None:
    """Providers meter prompt + reserved completion together.

    A fixed batch size sends requests larger than a per-minute quota allows, and
    the provider rejects those outright rather than queueing them.
    """
    from selfcorpus.translate import (
        OUTPUT_RATIO,
        TOKEN_BUDGET,
        estimate_tokens,
        plan_batches,
    )

    class _Doc:
        def __init__(self, text: str) -> None:
            self.text = text

    documents = [_Doc("word " * 300) for _ in range(12)]
    batches = plan_batches(documents, budget=700)
    assert sum(len(batch) for batch in batches) == len(documents)
    for batch in batches:
        prompt = sum(estimate_tokens(doc.text) for doc in batch)
        assert prompt <= 700 or len(batch) == 1
        # Prompt plus the reservation sized from it must still fit the quota.
        assert prompt + prompt * OUTPUT_RATIO <= TOKEN_BUDGET or len(batch) == 1


def test_plan_batches_keeps_an_oversized_section_alone() -> None:
    """An outsized section is isolated so the provider rejects it, not its neighbours."""
    from selfcorpus.translate import plan_batches

    class _Doc:
        def __init__(self, text: str) -> None:
            self.text = text

    huge, small = _Doc("word " * 5000), _Doc("tiny")
    batches = plan_batches([huge, small], budget=700)
    assert [len(batch) for batch in batches] == [1, 1]
