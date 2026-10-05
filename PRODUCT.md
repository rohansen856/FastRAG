# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

- **Recruiters and portfolio viewers** assessing the team's engineering. They arrive at the
  marketing site with little time, and judge the work by what they can see run: the hero ask
  box, the launch film, the `/query` trace, the architecture diagrams and the published
  benchmarks.
- **End users asking questions** about FastRAG itself, typed or spoken, in English or an Indian
  language. They want an answer they can check, and they get its sources with it.

The site credits one developer, set by `NEXT_PUBLIC_DEVELOPER` in `website/.env`.

## Product Purpose

FastRAG is a voice-enabled, multilingual, source-grounded RAG service. A question passes
guardrails, cache, hybrid retrieval, reranking and corrective retrieval (CRAG), and is
answered only from retrieved chunks, with every sentence's citation validated. When the
evidence is too weak it abstains, and when the input is unsafe or an injection it refuses.

Success is an answer whose every sentence points at a real source, or an honest "I don't know
based on the available sources", never a fluent guess.

## Positioning

**Cited or silent.** Neighbouring RAG demos answer whatever they are asked. FastRAG validates
each sentence's citation against the chunks it actually retrieved, gates the answer on a
calibrated reranker threshold, and exposes every decision (scores, thresholds, the CRAG
action, timings) in a trace anyone can open and re-run. Speed, voice and multilingual support
are supporting claims, not the lead.

## Operating Context

- The hosted demo runs the `cloud` profile: website, operator console and FastAPI function on
  Vercel, with Qdrant Cloud, Neon, Redis Cloud, Jina, Groq and Sarvam behind them. The `local`
  profile runs the same pipeline on Docker Compose with in-process ONNX models.
- The indexed corpus is FastRAG's own code and docs (the self-corpus), in English plus Hindi,
  Bengali, Tamil, Telugu and Marathi.
- Visitors meet the product through the `website/` landing page (ask box, chat answers, demo
  film), its `/docs` section and the `/query` pipeline trace. The `web/` operator console is
  an internal tool.
- Runs and traces live only in the visitor's browser tab (`sessionStorage`); nothing is stored
  server-side per visitor.

## Capabilities and Constraints

- Text and voice questions (Sarvam speech-to-text, browser audio re-encoded to 16 kHz WAV),
  streamed answers over SSE, document upload scoped to the session.
- Six chunking strategies, two provider profiles, exact and semantic answer caches.
- The query token is server-only; the browser always goes through the site's API proxy.
- The service refuses to start without a real calibration file pinned to the indexed content.
- Per-request overrides (the `/query` Experiment panel) are off on the hosted cloud deployment.
- The 200 ms retrieval target applies to the local profile; cloud-profile timings are network
  bound and are labelled as such.
- Known gap: Tamil and Telugu questions currently receive English answers.
- Undecided: the repository has no licence file, although the site calls the project open
  source. Do not state a specific licence until one is added.

## Brand Commitments

- The name **FastRAG**, written as one word, with the small **OSS** tag beside it in the
  navigation.
- The speedometer mark (`website/public/logo.svg`, `website/public/icon.svg`).
- The line "Answers only from retrieved sources - or it stays silent."
- The launch film (YouTube `7SnSBCGezbU`, 30 s), whose headline is "Cited or silent."

## Evidence on Hand

- Published latency benchmarks for both profiles (`docs/latency.md`), and a golden evaluation
  set and calibration data under `eval/`.
- Three real recorded runs from the hosted API, one per outcome
  (`website/public/query-examples/`).
- The launch film and its poster frame (`website/public/demo/`).
- Twelve architecture diagrams with source citations (`docs/diagrams/`).
- There are no customer logos, user testimonials, usage numbers or press. Never fabricate
  them; the site's "achievements" are statements about the system, not quotes from people.

## Product Principles

1. **Show the source or say nothing.** Every claim, in the product and about it, should be
   traceable to code, data or a recorded run.
2. **Make the pipeline visible.** Decisions (guardrails, gates, CRAG, citations) are shown,
   not hidden; a visitor should be able to see why an answer exists or doesn't.
3. **Label numbers honestly.** Say which profile a number comes from and what it measures.
4. **Fail closed on answers, open on extras.** Retrieval, rerank, generation and citations
   fail closed; cache, telemetry and optional safety checks fail open.

## Accessibility & Inclusion

Questions and the hero headline cycle through Indian scripts (Devanagari, Bengali, Gurmukhi,
Gujarati, Odia, Tamil, Telugu, Kannada, Malayalam, Urdu). Text rendering must keep Indic
conjuncts and matras intact: animate whole words, never split them by code unit. Voice input
is an alternative to typing, not a replacement for it.
