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
