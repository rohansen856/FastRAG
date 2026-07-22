from fastrag.evaluation import EvaluationRecord, GoldenItem, check_thresholds, deterministic_metrics


def test_deterministic_metrics():
    answerable = GoldenItem(
        id="a",
        query="q",
        reference_answer="answer",
        answerable=True,
        relevant_chunk_ids=["c1"],
        reference_contexts=["context"],
        category="factual",
    )
    unanswerable = GoldenItem(
        id="b",
        query="q2",
        reference_answer=None,
        answerable=False,
        category="no-answer",
    )
    records = [
        EvaluationRecord(
            answerable,
            {"outcome": "answered", "citations": [{"chunk_id": "c1"}]},
            ["c1"],
            ["c1"],
            ["context"],
        ),
        EvaluationRecord(
            unanswerable,
            {"outcome": "no_answer", "citations": []},
            [],
            [],
            [],
        ),
    ]
    metrics = deterministic_metrics(records)
    assert metrics == {
        "recall_at_20": 1.0,
        "mrr_at_5": 1.0,
        "valid_citation_rate": 1.0,
        "false_answer_rate": 0.0,
    }


def test_threshold_checker_requires_all_metrics():
    assert check_thresholds({"recall_at_20": 1.0, "false_answer_rate": 0.0})
