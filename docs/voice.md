# Voice input

Voice is a stage in front of the existing pipeline, not a separate pipeline. Audio becomes
text, and from that point every guardrail, retrieval, CRAG, and citation rule behaves exactly
as it does for typed input. The transcript is carried through and returned so the user can
see what the system actually heard - most "wrong answer" reports on voice systems are
transcription errors, and hiding the transcript makes them impossible to diagnose.

## Endpoints

| Endpoint | Purpose |
|---|---|
| `POST /v1/transcribe` | Audio to text only. Returns a `Transcript`. |
| `POST /v1/voice/query` | Transcribe, then answer. Returns a full `QueryResponse`. |
| `POST /v1/voice/query/stream` | Same, as SSE. Emits `transcript` first, then the normal `meta` / `answer_chunk` / `final` events. |

All three take a `multipart/form-data` body with a `file` field and optional `language` and
`strategy` fields, and all three require the query bearer token.

```bash
curl -fsS -H "Authorization: Bearer $FASTRAG_QUERY_API_KEY" \
  -F file=@question.wav -F language=hi \
  https://your-api.onrender.com/v1/voice/query
```

The `transcript` SSE event arriving before any answer token is deliberate: the UI shows what
was heard while retrieval is still running, so the user can tell immediately that a
misheard question is about to produce a wrong answer.

Uploads above `FASTRAG_STT_MAX_BYTES` (12 MB default) are rejected with 413 before reaching
the provider, so a bad client cannot spend your STT quota.

## Providers

**Sarvam Saaras v3** is the default. Two things differ from most APIs:

- Authentication uses an `api-subscription-key` header, not `Authorization: Bearer`.
- `FASTRAG_SARVAM_MODE` chooses between `transcribe`, which keeps the source language, and
  `translate`, which returns English regardless of input.

That mode choice has a real retrieval consequence. `translate` means a Hindi question
searches English chunks, which works well if your corpus is mostly English but throws away
the Indic-language passages you indexed. `transcribe` keeps the question in its original
language and relies on the multilingual embedding model to match same-language passages.
For the MSMARCO-XI corpus, which is indexed per-language, `transcribe` is the right default.

**ElevenLabs Scribe** is available as an alternative via `FASTRAG_STT_PROVIDER=elevenlabs`.

If no key is configured, `active_stt_provider` resolves to `none` and the three voice
endpoints return 503 with `{"stage": "stt"}`. Text queries are unaffected - voice is
optional, not a hard dependency.

## Audio format

The browser records WebM/Opus, which neither provider reliably accepts, so both frontends
re-encode client-side: [`web/lib/audio.ts`](../web/lib/audio.ts) and
[`website/lib/audio.ts`](../website/lib/audio.ts) decode through an `AudioContext` and emit
16 kHz mono WAV before upload. That keeps ffmpeg off the 512 MB Render instance, and 16 kHz
mono is what the speech models expect, so the conversion loses nothing.

Sarvam's REST endpoint caps at 30 seconds of audio. Longer recordings need the WebSocket
streaming API, which is not wired up here.

## Latency

Speech-to-text is a network round trip to a provider and is reported as its own `stt_ms`
stage, kept out of the retrieval-pipeline total. It is not part of the 200ms retrieval
target and cannot be made to fit inside one; presenting a blended number would misrepresent
both. See [latency.md](latency.md).
