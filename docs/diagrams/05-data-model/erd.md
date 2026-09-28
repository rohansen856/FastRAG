# FastRAG data model (ERD)

Companion to the interactive entity map in [`data-model.html`](data-model.html). Attributes and
cardinalities are taken from the code at commit `41815d0`; the source for each entity is listed
below the diagram.

Only `index_manifests` is a relational table. The Qdrant, Redis and file entities are documents
or keys, and **every relationship is logical**: no store enforces a foreign key, so the code keeps
them consistent.

```mermaid
erDiagram
    INDEX_MANIFESTS {
        text index_version PK
        text collection_name "kb_{version}"
        text content_version
        text embedding_fingerprint
        text state "building|validated|active|retired|failed"
        jsonb manifest "IndexManifest + centroid"
        timestamptz created_at
        timestamptz activated_at "nullable"
    }
    QDRANT_COLLECTION {
        string name PK "kb_{version}"
        vector dense "cosine, HNSW m=16"
        sparse bm25 "IDF modifier"
    }
    QDRANT_ALIAS {
        string name PK "kb_current"
        string collection FK
    }
    CHUNK_POINT {
        uuid chunk_id PK "uuid5(document_id:strategy:normalized_text)"
        string document_id FK
        string strategy "keyword index"
        string language "keyword index"
        string title
        string source_uri
        int page
        int position
        string text "normalized"
        string raw_text "optional, pre-normalisation"
        string context_text "optional"
        bool session_upload "uploads only, bool index"
    }
    SOURCE_DOCUMENT {
        string document_id PK "sha256(self:lang:path:symbol)[:24] or user-<hex>"
        string title
        string source_uri "GitHub blob @ commit or docs page"
        string language
    }
    CALIBRATION {
        float reranker_threshold
        float crag_confident_threshold
        float cache_distance_threshold
        float offtopic_threshold
        string embedding_fingerprint
        string reranker_fingerprint
        string content_version FK
        float false_answer_rate "<= 0.05"
        int sample_count ">= 30"
    }
    CORPUS_CENTROID {
        float_array centroid "L2-normalised mean vector"
        string index_version FK "manifest.centroid or config file"
    }
    CACHE_NAMESPACE {
        string hash PK "sha256(...)[:24], derived, not stored"
        string content_version
        string embedding_fingerprint
        string prompt_version
        string generator_model
        int max_tokens
        string locale
        string chunk_strategy
        string document_scope
    }
    EXACT_CACHE_ENTRY {
        string key PK "fastrag:exact:{ns}:{sha256(query)}"
        json payload "answer, citations[], outcome"
        int ttl_seconds "604800"
    }
    SEMANTIC_CACHE_ENTRY {
        string key PK "fastrag:semantic:{fp16}:{uuid}"
        tag namespace FK
        json payload "answer, citations[], outcome"
        float32_vector embedding "RediSearch HNSW, cosine"
    }
    GOLDEN_ITEM {
        string id PK "self-{lang}-{sha1(question)[:10]}"
        string query
        string reference_answer "null when unanswerable"
        bool answerable
        string_array relevant_chunk_ids
        string category
        string language
    }
    CACHE_PAIR {
        string left
        string right
        bool equivalent
    }

    INDEX_MANIFESTS ||--|| QDRANT_COLLECTION : "collection_name"
    QDRANT_ALIAS |o--|| QDRANT_COLLECTION : "points at"
    INDEX_MANIFESTS ||--o| CORPUS_CENTROID : "manifest.centroid"
    CALIBRATION }o--|| INDEX_MANIFESTS : "content_version"
    QDRANT_COLLECTION ||--o{ CHUNK_POINT : "contains"
    SOURCE_DOCUMENT ||--|{ CHUNK_POINT : "document_id (per strategy)"
    GOLDEN_ITEM }o--o{ CHUNK_POINT : "relevant_chunk_ids"
    EXACT_CACHE_ENTRY }o--o{ CHUNK_POINT : "citations[].chunk_id"
    SEMANTIC_CACHE_ENTRY }o--o{ CHUNK_POINT : "citations[].chunk_id"
    CACHE_NAMESPACE ||--o{ EXACT_CACHE_ENTRY : "key segment"
    CACHE_NAMESPACE ||--o{ SEMANTIC_CACHE_ENTRY : "namespace TAG"
```

## Rules the diagram cannot show

- **At most one `active` row.** A partial unique index, `one_active_index`, enforces this.
  `activate()` retires the current active row and promotes a `validated` one inside the same
  connection.
- **A collection is recreated if its name exists.** A build that reuses an index version drops
  and recreates `kb_{version}`, and re-registering that version resets its row to `building`.
- **Uploads share the live collection.** Session uploads are chunk points written into the
  active collection with `session_upload = true`. Unscoped searches exclude them, and they have
  no TTL.
- **Cache entries scope themselves.** Namespace inputs include `content_version`, so a new
  index makes earlier entries unreachable rather than deleting them. They expire after 7 days.
- **Calibration is pinned to the index.** It is fitted against one `content_version`, and
  startup fails readiness when the active index differs.

## Sources

| Entity | Code |
|---|---|
| `index_manifests` | `src/fastrag/registry.py:15-59`, `:95-109` |
| Qdrant collection and alias | `src/fastrag/indexing.py:109-111`, `:187-212`, `:290-304`; `src/fastrag/config.py:43` |
| Chunk point | `src/fastrag/chunking.py:328-367`; `src/fastrag/indexing.py:224-237`; `src/fastrag/ingest_document.py:103-104` |
| Source document | `src/fastrag/chunking.py:34-42`; `scripts/selfcorpus/sources.py:147-158`; `src/fastrag/ingest_document.py:71` |
| Calibration | `src/fastrag/calibration.py:12-80`; `src/fastrag/calibrate.py:184-200` |
| Corpus centroid | `src/fastrag/registry.py:194-213`; `src/fastrag/indexing.py:266-280` |
| Cache namespace and entries | `src/fastrag/fingerprint.py:26-50`; `src/fastrag/adapters/cache.py:53-215` |
| Golden item and cache pair | `scripts/selfcorpus/golden.py:105-124`, `:446-484`; `src/fastrag/evaluation.py:19-34` |
