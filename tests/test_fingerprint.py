from fastrag.fingerprint import EmbeddingFingerprint, cache_namespace


def test_embedding_fingerprint_changes_with_query_prefix():
    base = EmbeddingFingerprint("model", "revision", "sha", 768)
    prefixed = EmbeddingFingerprint("model", "revision", "sha", 768, query_prefix="query: ")
    assert base.digest != prefixed.digest


def test_cache_namespace_changes_with_content_version():
    common = dict(
        embedding_fingerprint="embedding",
        prompt_version="v1",
        generator_model="model",
        max_answer_tokens=200,
    )
    assert cache_namespace(content_version="one", **common) != cache_namespace(
        content_version="two", **common
    )
