# Chunking strategies

There is no chunk size that is right for every corpus. MS MARCO passages are short and
self-contained; an ingested policy PDF is long and structured. Rather than pick one and
defend it, [`src/fastrag/chunking.py`](../src/fastrag/chunking.py) implements six strategies
and writes a `strategy` field into every Qdrant payload, so all six can live in one
collection and be compared at query time with a filter.

Pass `strategy` on `/v1/query` to pick one; omit it to search across all indexed strategies.
`GET /v1/strategies` reports which are available and which are actually indexed.

## The six

**`fixed`** - uniform word windows with overlap. The baseline. Fast, predictable, and it
will happily cut a sentence in half.

**`sentence`** - packs whole sentences up to a word budget and never splits mid-sentence.
Overlap carries trailing sentences into the next chunk so a fact that spans a boundary still
appears intact somewhere.

**`sentence_window`** - indexes one sentence but returns its neighbours. A single-sentence
vector is tightly focused, which improves retrieval precision, but a lone sentence often
cannot answer anything on its own; the returned window restores the context it needs.

**`semantic`** - embeds consecutive sentences and cuts where similarity drops. The cut point
is a percentile of the similarity distribution actually observed in that document rather
than a fixed constant, so it adapts instead of being tuned for one corpus. This is the
expensive one at ingest time: it embeds every sentence.

**`hierarchical`** - small children are retrieved, large parents are generated from. Same
idea as `sentence_window` at a coarser granularity.

**`metadata_aware`** - prepends `title | language | query` as a header to the embedded text.
A bare MS MARCO passage frequently never names the entity it is about, and this restores
that signal. The citation excerpt still shows the untouched passage, so the header never
leaks into what the user reads.

## Indexed text versus generated text

Three strategies deliberately separate the two. `sentence_window` and `hierarchical` return
more than they index; `metadata_aware` indexes more than it returns. Both directions are
expressed through a `context_text` payload field, and `context_of()` is what the pipeline
calls when assembling the generation context.

The chunk text is what gets embedded and cited. The context text is what the model reads.
Keeping these separate is what lets retrieval precision and generation context be tuned
independently.

## Comparing strategies honestly

The strategy name is part of the cache namespace in
[`fingerprint.py`](../src/fastrag/fingerprint.py), so an A/B comparison cannot accidentally
serve a cached answer produced under a different strategy. It is also recorded in the index
manifest alongside the languages and chunk count.

The `StrategyCompare` panel in the web UI runs one query against each indexed strategy and
shows outcome, sources, and latency side by side. That is the intended way to choose one:
measure on your corpus, do not reason about it from first principles.

## Cost

Indexing every strategy multiplies the vector count by roughly the number of strategies -
more for `sentence_window`, which produces one chunk per sentence. On Qdrant's 1 GB free
tier this is the binding constraint, which is why `scripts/ingest-msmarco.py` takes a
`--max-chunks` cap. In production you index the one strategy you chose, set
`FASTRAG_CHUNK_STRATEGIES` to it alone, and the multiplier disappears.

`FASTRAG_CHUNK_SIZE` and `FASTRAG_CHUNK_OVERLAP` apply to the strategies that take a budget
(`fixed`, `sentence`, `semantic`, `metadata_aware`).

## Multilingual splitting

Sentence splitting uses `SENTENCE_TERMINATORS` from [`text.py`](../src/fastrag/text.py),
which includes the Devanagari danda `।` and its double form alongside ASCII terminators.
An English-only `[.!?]` splitter returns Hindi, Bengali, and Marathi documents as one
enormous sentence, which silently defeats every sentence-based strategy and breaks
sentence-level citation streaming. The same regex is used by the citation validator for
exactly that reason.
