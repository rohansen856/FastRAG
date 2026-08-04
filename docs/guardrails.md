# Guardrails

Grounding was already enforced on the way out: calibrated abstention, sentence-level citation
validation, and markers that must refer to chunks actually supplied. What was missing was the
way in. [`src/fastrag/guardrails.py`](../src/fastrag/guardrails.py) rejects input that is
obviously unanswerable or hostile before it costs an embedding call, a retrieval, and a
generation.

Disable with `FASTRAG_GUARDRAILS_ENABLED=false`.

## Ordered cheapest-first

The ordering is the design. Each check runs only if the previous one passed, and the
expensive ones are last.

**1. String checks - microseconds, no network.**

- *Empty* input.
- *Prompt injection*: patterns for instruction override ("ignore previous instructions",
  "developer mode"), system-prompt extraction, and injected `<system>` / `[system]` role
  markers.
- *Unsafe content*: a narrow denylist covering weapons of mass destruction, targeted
  violence, CSAM, and attacks on critical infrastructure. Narrow on purpose - a broad
  keyword denylist blocks legitimate factual questions and is worse than useless on a
  retrieval system whose answers are constrained to the corpus anyway.
- *Language gate*: the detected script must be in `FASTRAG_GUARDRAIL_LANGUAGES`. Unknown
  scripts pass, because a false block is worse than a search that returns nothing.

**2. Off-topic - one dot product.**

Cosine similarity between the query vector and the corpus centroid. This reuses the
embedding the pipeline computed anyway, so the marginal cost is a dot product rather than
another provider round trip. Below the calibrated threshold, the query is off-topic and is
refused without touching Qdrant.

The centroid and its threshold are produced during calibration from the same held-out set as
the other thresholds. Without a calibration artifact the check is skipped rather than
guessed at.

**3. Model safety check - optional, one LLM call.**

Only for input the patterns did not settle, and only when a safety generator is configured.
It uses JSON-schema-constrained output and **fails open**: if the classifier is down or slow,
the query proceeds. A safety classifier outage taking the entire service offline is a worse
failure than one unsafe question reaching a model that is already constrained to answering
from the corpus.

## Refusals are specific

Each rule has its own message. "That question is outside the knowledge base I have been
given" and "I can't help with that request" are different situations, and collapsing them
into one generic refusal leaves the user unable to tell a fixable mistake from a policy
decision.

A guardrail block produces the `REFUSED` outcome, which is deliberately distinct from the
`NO_ANSWER` that abstention produces. `REFUSED` responses are never cached - a rule change
or a re-index should take effect immediately rather than being pinned by a stale entry.

## Observability

The `guardrail` field on the response carries the rule, a detail string, and the similarity
score for off-topic blocks. The web UI's decision trace shows it, so a user who is blocked
can see which rule fired and why. `guardrail_blocks` is a Prometheus counter labelled by
rule; a spike in `prompt_injection` is an attack signal, while a spike in `off_topic`
usually means the corpus does not cover what people are asking for.

## What guardrails do not do

They do not replace output-side grounding. A question that passes every input check can
still retrieve nothing relevant, and the abstention gate and citation validator remain the
things that stop an ungrounded answer. Input guardrails cut cost and block hostile input;
they are not the last line of defence.
