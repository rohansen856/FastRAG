# Corrective RAG

Plain RAG generates from whatever retrieval returned, however bad it was. CRAG grades the
retrieved context first and takes a corrective action when it is weak. That is what stops a
fluent, confident answer being built on the wrong passage.

Implementation: [`src/fastrag/crag.py`](../src/fastrag/crag.py). Disable with
`FASTRAG_CRAG_ENABLED=false`.

## The grader is the reranker

The usual CRAG design calls a second LLM to grade relevance. That costs hundreds of
milliseconds per query, and this pipeline has a 200ms retrieval budget, so it is not an
option here.

Instead the grader is the reranker score that was already computed. Every candidate has
been scored by the cross-encoder as part of normal retrieval, so grading costs a comparison
against two thresholds and nothing else. Both thresholds come from
[`calibrate.py`](../src/fastrag/calibrate.py) and live in `config/calibration.json` next to
the existing abstention threshold.

## Three bands, three actions

**Above `crag_upper` - `CORRECT`.** Retrieval is good. Generate directly, no correction, no
added latency. This is the common case and it is why CRAG does not move the median.

**Between the thresholds - `AMBIGUOUS`, so refine.** A passage often lands mid-band because
one genuinely relevant sentence is buried in noise. The chunk is decomposed into sentence
strips, the strips are re-scored by the same reranker, and only those above the abstention
threshold are kept. Strips shorter than `FASTRAG_CRAG_STRIP_MIN_TOKENS` keep their original
chunk instead, because trimming below that point leaves too little to support a citation.
If nothing survives, the original ranking is used unchanged rather than generating from
nothing.

**Below `reranker_threshold` - `INCORRECT`, so rewrite once.** The generator rewrites the
query under a JSON schema - expanding abbreviations, adding entity names, keeping the
original language - and retrieval runs again. If the second attempt clears the threshold,
its results are used. If not, the system abstains.

The rewrite is capped at one iteration by `FASTRAG_CRAG_MAX_REWRITES`. An uncapped loop is
how a CRAG implementation turns a query that has no answer in the corpus into a multi-second
hang, and abstaining is the correct outcome for that query anyway.

## Failing toward abstention

Every failure path in the rewrite branch abstains. If the rewrite call raises, if it returns
an empty string, if it returns the original query unchanged, or if the retry still scores
below threshold, the result is "I don't know" - never a generated answer. A correction step
that cannot complete must not become a licence to answer without grounding.

## What you see

The `crag` field on the response carries the action taken, the top reranker score, the
number of strips kept, and the rewritten query when there was one. The `web/` console decision
trace renders this directly, so a surprising answer can be traced to the band it fell into.
A `crag_actions` Prometheus counter is labelled by action, which is the fastest signal that
retrieval quality has drifted: a rising `incorrect` share means the corpus no longer covers
what people are asking.

## Benchmarking

`FASTRAG_CRAG_ENABLED=false` gives the clean retrieval-only latency number. With CRAG on,
`crag_ms` is reported as its own stage inside the retrieval pipeline total, so its cost is
visible rather than absorbed. Expect near-zero at P50, since most queries grade `CORRECT`,
and a visible tail at P95 and P100 where refinement and rewrites happen. That shape is the
point: correction is paid for only by the queries that need it.
