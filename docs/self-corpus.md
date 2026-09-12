# The self-corpus

FastRAG's default corpus is FastRAG: its documentation, its Python source, and its
deployment configuration. Ask the deployed service how CRAG grades retrieval and it answers
from [`docs/crag.md`](crag.md) and `src/fastrag/crag.py`, citing both.

Build it with [`scripts/ingest-self.py`](../scripts/ingest-self.py). The MSMARCO-XI corpus
remains available through [`scripts/ingest-msmarco.py`](../scripts/ingest-msmarco.py); see
[benchmarking.md](benchmarking.md) for which corpus the published numbers are measured on.

## What is indexed

`git ls-files` supplies the file list, so the corpus never picks up build output or anything
else `.gitignore` excludes, and the same command produces the same corpus on any machine.

| Included | Why |
|---|---|
| `docs/*.md`, `README.md`, `AGENTS.md` | The prose that answers "how does this work" |
| `src/fastrag/**/*.py`, `scripts/*.py` | The implementation behind every claim the prose makes |
| `compose.yaml`, `render.yaml`, `pyproject.toml`, `.env.*.example` | Deployment and configuration questions |

Frontend TypeScript is excluded. Fifty-seven of its files are vendored shadcn primitives, and
the surrounding JSX dilutes retrieval without answering questions anyone asks.

## Documents are sections, not files

`pipeline.py` is 787 lines; a chunk drawn from its middle answers nothing cleanly. So files
are split before chunking:

- **Markdown** splits on `##` headings, with the preamble kept under the file title.
- **Python** splits on the AST: one document per top-level `def`/`class`, plus a module
  header holding the docstring, imports and constants. This is not only tidiness.
  `SENTENCE_END_RE` in [`text.py`](../src/fastrag/text.py) treats both newlines and
  `.` + whitespace as sentence ends, and `self._registry.activate(...)` is full of both, so
  letting the sentence chunker loose on raw source lands chunk boundaries mid-function.
- **Config files** stay whole.

That turns 74 tracked files into 436 English documents - the corpus grows as the repository
does, this file included - and roughly 950 more once the prose sections are
translated. Each carries a `section` in its metadata,
which is what `metadata_aware` chunking embeds as a header — the role MS MARCO's `query`
field used to play.

`document_id` hashes the **repo-relative** path. `IndexBuilder._load_documents` hashes the
resolved absolute path, which differs between a laptop and CI and would make every golden
`relevant_chunk_id` non-portable.

## Citations link to real code

The MS MARCO corpus used synthetic `msmarco-xi://` URIs, and `CitationLink` in the website
only builds an anchor for `^https?://`, so citations rendered as inert text. Here
`source_uri` is a GitHub blob URL pinned to the **ingested commit**, with line anchors
(`#L45-L49`), so a citation keeps pointing at the code that was actually indexed rather than
at whatever `master` drifted to. Pass `--site-url` to send documentation citations to the
marketing site's `/docs/<slug>` route instead.

### Readable code excerpts

Every chunking strategy joins its pieces with spaces, and `normalize_text` then collapses
whitespace — right for embedding and cache stability, useless for reading Python. Chunks
therefore carry a `raw_text` payload field with the verbatim text, and citations and trace
excerpts render from it.

This recovers the original layout for any chunk that covers a whole document, which is about
83% of them once files are split per section and per function. The rest — sections too long
for one chunk — still render collapsed, and the line-anchored `source_uri` is how you read
those. `raw_text` is absent when it would equal `text`, and `chunk_id` hashes the
*normalised* text, so adding the field changed no chunk ids.

## Multilingual

The `language` payload filter, the six-language golden split and
`FASTRAG_GUARDRAIL_LANGUAGES` all assume chunks exist in each language. An English-only
corpus would leave `language=hi` matching zero points, so the prose docs are machine
translated into Hindi, Bengali, Tamil, Telugu and Marathi at ingest. MSMARCO-XI is itself a
machine translation of MS MARCO; this is the same bargain, made explicit.

Only prose is translated. A translated identifier answers nothing, and
`detect_script_language` would read the result as English anyway — which is also why every
translated document sets `language=` explicitly instead of relying on detection: a Hindi
translation of `deployment.md` keeps its Latin-script code fences and env-var names, and
character counting would miscount it as English.

Translation happens per **section**, not per file, and each translated section keeps the
`document_key` of the English section it came from. This matters more than it sounds:
translating a Markdown `##` heading changes the section title, so translating whole files and
re-splitting them would key each translation on its translated heading, and no Indic golden
item could ever be matched to its chunks. A section and its translations share a key and have
different ids — the shared key is what lets a question be relabelled across languages, and the
different ids are what stop their chunks colliding.

Translations are cached under `eval/translations/<lang>/`, one file per section, so re-ingest
is cheap, each translation is reviewable on its own, and a failed run keeps the work it
already did. A section that fails to translate is reported and skipped rather than taking the
run down.

Indic golden items are grounded to translated-prose chunks only. Code chunks are tagged
`language=en`, so a Bengali question labelled with a code chunk becomes unretrievable the
moment a language filter is applied.

## Golden labels are derived, not invented

MS MARCO gives its labels away in the `is_selected` column. A self-corpus has to derive
them, and the split of responsibility is the point:

- **The generator writes the questions.** One per section, from that section's text.
- **The chunker assigns the labels.** `relevant_chunk_ids` are the chunk ids that section
  actually produced under the golden strategy, read out of the same in-memory list handed to
  the index builder. A label cannot drift from what was indexed, and the run hard-fails if
  any label names a chunk that is not in the final collection — a check
  `scripts/check-golden.py` cannot make, because it validates the schema and has no chunk set.

Three constraints the script enforces, each of which would otherwise zero out every metric:

- `--golden-strategy` must be the **first** configured strategy. `evaluation.collect_records`
  and `calibrate.run` both retrieve with `chunk_strategy_list[0]`.
- `semantic` and `metadata_aware` are rejected as golden strategies. `semantic` derives
  boundaries from float embeddings, so ids move with numerical noise; `metadata_aware` hashes
  the title into the chunk text, so ids move when a file is renamed.
- Chunks are deduplicated before the builder sees them, because
  `IndexBuilder._validate_collection` asserts the indexed point count equals `len(chunks)`.

### Unanswerable items are verified, not trusted

Unanswerable questions are written from capabilities FastRAG genuinely lacks, then **checked
against the built index**. A file exclusion is not a semantic exclusion: this repository
documents itself twice over, and `chunking.py`'s module docstring will happily answer a
question written from `docs/chunking.md`. Each candidate is scored by the real retriever and
reranker, and anything scoring like an answerable item is dropped as a leak. With fifty
unanswerable items, three leaks fail the ≤0.05 false-answer gate.

Answerable items are never filtered this way. Dropping a question because retrieval missed it
is tuning the golden set to pass its own gate.

The questions are in-domain near-misses on purpose. An obviously off-topic question is
stopped by the text guardrail and returns `refused` without ever reaching the reranker, so it
calibrates nothing while still scoring as a correct abstention.

## Calibration is genuinely held out

The shipped `eval/calibration.jsonl` was the first 40 rows of `eval/golden.jsonl`, all
Bengali: thresholds fitted on data that was also in the regression set, in one language out
of six. The self-corpus generator splits one pool **by source document**, stratified across
languages and answerability, so two questions written from the same section cannot straddle
the split.

The script fails early, naming the downstream bound, rather than three commands later:

| Bound | Owner |
|---|---|
| golden ≥ 200 items, ≥ 25% unanswerable, unique ids | `evaluation.load_golden` |
| calibration ≥ 30 items | `calibrate.run` and `Calibration.from_dict` |
| calibration ≥ 40 **negatives** | `choose_gate` |
| ≥ 30 cache pairs | `calibrate.run` |

The 40-negative floor is arithmetic, not taste. `choose_gate` needs some threshold with
`false_positives / negatives ≤ 0.05`; with 28 negatives a single false positive is already
0.036 and a second is 0.071, so calibration aborts with "no reranker threshold satisfies
false-answer-rate constraint". On a corpus where code and docs chunks are all mutually
similar, that happens easily.

Semantic-cache pairs are drawn from the calibration split only. Positives are real
paraphrases rather than the old `"Please answer: " + query`, which shared almost every token
and taught the threshold nothing. Negatives are in-domain near-misses; random unrelated pairs
are trivially separable and let `choose_cache_distance` settle on a uselessly permissive gate.

## Corpus size and what the golden gate measures

At `FASTRAG_CHUNK_SIZE=400` the English self-corpus yields roughly 90 `sentence` chunks.
Retrieving the top 20 from 90 is over a fifth of the corpus, so `recall_at_20 >= 0.95` becomes
nearly free and stops discriminating. Section and AST splitting already multiplies the
document count; at `FASTRAG_CHUNK_SIZE=150` the English corpus measures 645 `sentence` chunks
(1,290 across `sentence` and `metadata_aware` together), and roughly twice that once the five
translations are indexed alongside. Small, but no longer degenerate.

Be honest about the consequence: on a corpus this size, recall@20 is a smoke test. MRR@5,
faithfulness, correctness and citation validity still mean something. Published latency and
quality numbers stay measured on MSMARCO-XI.

`sentence_window` produces roughly 9,400 chunks on the same corpus. Using it as the golden
strategy would make recall@20 discriminating again, but it must then also be moved to the
front of `FASTRAG_CHUNK_STRATEGIES`, which changes the pipeline's default retrieval
behaviour — a larger decision than it looks.

## Deriving the set without a generator

`scripts/derive-eval.py` builds the same records from corpus structure alone: a
Markdown heading names its section, a Python symbol names itself, and a section's
opening prose is its reference answer. Unanswerable items are templated over a
list of capabilities the repository genuinely lacks. No generator is called.

This exists because of an ordering problem rather than a preference. A freshly
indexed corpus cannot be served at all until some calibration matches it - every
threshold is fitted against one corpus and startup checks which - so a generator
quota that runs out leaves a built index that nothing is allowed to query.
Deriving the set closes that gap in one command:

```bash
uv run python scripts/derive-eval.py --collection kb_<version>
uv run python -m fastrag.calibrate \
  --golden eval/calibration.jsonl --cache-pairs eval/cache_pairs.jsonl
```

It reads an existing collection and re-embeds nothing: chunk ids are a hash of
the chunk text, so they are recomputed locally and checked against the live
collection before anything is written.

**Read the resulting numbers with the caveat.** A heading-derived question shares
vocabulary with the chunk it points at, so retrieval finds it more easily than a
real user's phrasing would, and thresholds fitted on it are optimistic. It is a
bootstrap, not a replacement: regenerate with `ingest-self.py` when quota allows
and recalibrate.

## Provider quotas shape the run

Ingest is the most provider-hungry thing this repository does, and free tiers meter it two
ways at once. Groq's free tier allows 1000 requests per day and **8000 tokens per minute**,
and that per-minute quota covers the prompt *and* whatever `max_tokens` reserves, whether or
not the reservation is used. A fixed `max_tokens` large enough for a long translation is
therefore rejected outright next to any real input, rather than queued.

So batches are planned by estimated tokens, not by section count, and `max_tokens` is sized
from the input. Two consequences worth planning around:

- **The daily budget binds before the per-minute one.** Groq's free tier also caps
  tokens per *day* at 20,000, which is about five translation batches. A full
  multilingual pass is days of quota, not minutes; `--skip-eval` and
  `scripts/derive-eval.py` exist so an index can still be built and served in the
  meantime.
- **Translation is the slow part.** Roughly 1000 tokens per section round trip, times the
  number of sections and languages, divided by 8000 tokens per minute. A five-language pass
  over 126 sections is over an hour of wall clock on a free tier - not because anything is
  wrong, but because that is the quota. Run fewer languages first; the cache means the next
  run resumes rather than repeats.
- **Give ingest patient retries.** It is offline batch work, not a request path, so it can
  afford to wait out a rate limit that a live query never should:

  ```bash
  export FASTRAG_RETRY_MAX_ATTEMPTS=8
  export FASTRAG_RETRY_MAX_BACKOFF_SECONDS=90
  export FASTRAG_CIRCUIT_BREAKER_FAILURES=1000
  ```

  Without the last one the breaker - sized for a live request path - opens partway through
  and every remaining call fails fast against an open circuit. The generator is shared, so a
  run of translation failures would otherwise take question generation down with it.

`--max-questions` caps the English question-generation calls and samples across the corpus
rather than truncating, so a smaller budget still covers every file rather than the first few.

## Running it

Every threshold in `config/calibration.json` is a quantile of a score distribution measured
on one corpus. Re-indexing different content under unchanged models leaves the embedding and
reranker fingerprints matching, so the stale artifact used to load cleanly and be wrong in an
unknown direction. `calibrate` now records `content_version` and the pipeline checks it at
startup, so that case is a loud 503 on `/health/ready` instead of silent drift.

Cold start, with nothing serving yet:

```bash
docker compose up -d qdrant postgres redis
docker compose --profile tools run --rm model-init

# Inspect counts and the answerable/unanswerable split before touching Qdrant.
uv run python scripts/ingest-self.py --dry-run

uv run python scripts/ingest-self.py --site-url https://your-site.example
uv run python -m fastrag.calibrate \
  --golden eval/calibration.jsonl --cache-pairs eval/cache_pairs.jsonl

docker compose up -d api worker caddy      # wait for /health/ready to return 200

uv run python scripts/check-golden.py
uv run python -m fastrag.evaluation \
  --dataset eval/golden.jsonl --api-url http://localhost:8000
```

There is no circular dependency here: `fastrag.calibrate` builds its retriever in-process and
never calls the API. Only `fastrag.evaluation` needs a running service.

### Re-ingesting against a live deployment

`build_from_chunks` normally flips the `kb_current` alias as its last step. Between that flip
and the recalibration that follows, a running service answers from the new corpus using the
old corpus's thresholds and centroid. Use `--no-activate` to close that window:

```bash
# Builds and validates the new collection; the old corpus keeps serving.
uv run python scripts/ingest-self.py --no-activate

FASTRAG_QDRANT_ALIAS=kb_<version> uv run python -m fastrag.calibrate \
  --golden eval/calibration.jsonl --cache-pairs eval/cache_pairs.jsonl

uv run python scripts/ingest-self.py --activate <version> # flip the alias
```

Qdrant accepts a collection name wherever an alias is expected, which is what lets calibration
read the shadow collection. The centroid is staged to
`config/corpus_centroid.staged.json` and only moved into place when the alias flips — without
that, restarting the API mid-sequence would pick up the new centroid against the old
threshold and mark every query off-topic.

Rollback is the existing blue/green path: the previous collection is untouched, so pointing
`kb_current` back at it restores the old corpus.

`cache_namespace` includes `content_version`, so answers cached against the old corpus are
invalidated automatically — no flush needed.

Ingest and serve must use the same profile and `.env`;
`registry.assert_embedding_fingerprint` compares the active index's fingerprint against
running settings, and a centroid whose dimension does not match the embedding model is now
rejected at startup rather than silently returning cosine `0.0` for every query.

## Asking FastRAG about its own guardrails

One quirk worth knowing rather than fixing: the injection patterns in
[`guardrails.py`](../src/fastrag/guardrails.py) match on phrases like `developer mode`, so a
question *about* those patterns can trip them. "How does FastRAG detect prompt injection?"
and "show me the system prompt" both pass; "what is developer mode" and the possessive
"print your system prompt" are blocked. The pattern is doing its job, and weakening it so a
demo reads better would be the wrong trade.
