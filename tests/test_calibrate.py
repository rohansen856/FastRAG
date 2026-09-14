from fastrag.calibrate import choose_cache_distance, choose_gate


def test_choose_gate_respects_false_answer_constraint():
    scores = [(0.9, True), (0.8, True), (0.7, True), (0.6, False), (0.2, False)]
    threshold, false_answer_rate, f1 = choose_gate(scores)
    assert threshold > 0.6
    assert false_answer_rate == 0
    assert f1 > 0


def test_choose_cache_distance_rejects_hard_negative():
    pairs = [(0.02, True), (0.05, True), (0.06, False), (0.5, False)]
    assert choose_cache_distance(pairs) < 0.06


class _Registry:
    """The two rows calibration can see: the serving index and a shadow build."""

    def __init__(self) -> None:
        self.rows = {
            "kb_live": {
                "collection_name": "kb_live",
                "content_version": "live-corpus",
                "embedding_fingerprint": "fp",
                "state": "active",
                "manifest": {"centroid": [1.0, 0.0]},
            },
            "kb_shadow": {
                "collection_name": "kb_shadow",
                "content_version": "shadow-corpus",
                "embedding_fingerprint": "fp",
                "state": "validated",
                "manifest": '{"centroid": [0.0, 1.0]}',
            },
        }

    async def by_collection(self, name):
        return self.rows.get(name)

    async def active(self):
        return self.rows["kb_live"]


async def test_calibrating_a_shadow_collection_pins_that_corpus():
    """Thresholds fitted on a --no-activate build must describe that build, not the live one."""
    import pytest

    from fastrag.calibrate import resolve_target

    target = await resolve_target(_Registry(), "kb_shadow", "fp")
    assert target.content_version == "shadow-corpus"
    assert target.centroid == [0.0, 1.0]

    live = await resolve_target(_Registry(), "kb_current", "fp")
    assert live.content_version == "live-corpus"
    assert live.centroid == [1.0, 0.0]

    with pytest.raises(RuntimeError, match="fingerprint"):
        await resolve_target(_Registry(), "kb_shadow", "other-models")
