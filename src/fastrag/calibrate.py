from __future__ import annotations

import argparse
import asyncio
import json
import math
from pathlib import Path

from .bootstrap import (
    build_embedder_and_reranker,
    build_retriever,
    embedding_fingerprint,
    load_corpus_centroid,
    reranker_fingerprint,
)
from .config import Settings
from .evaluation import GoldenItem
from .model_artifacts import verify_configured_models


def choose_gate(scores: list[tuple[float, bool]]) -> tuple[float, float, float]:
    best: tuple[float, float, float] | None = None
    for threshold in sorted({score for score, _ in scores}):
        tp = sum(score >= threshold and label for score, label in scores)
        fp = sum(score >= threshold and not label for score, label in scores)
        fn = sum(score < threshold and label for score, label in scores)
        negatives = sum(not label for _, label in scores)
        false_answer_rate = fp / negatives if negatives else 0.0
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        candidate = (f1, -false_answer_rate, threshold)
        if false_answer_rate <= 0.05 and (best is None or candidate > best):
            best = candidate
    if best is None:
        raise RuntimeError("no reranker threshold satisfies false-answer-rate constraint")
    return best[2], -best[1], best[0]


def choose_confident_gate(scores: list[tuple[float, bool]], *, floor: float) -> float:
    """Upper CRAG band: the lowest score at which no unanswerable query gets through.

    Above this the context is trusted as-is. Between this and the abstention gate
    the context is treated as ambiguous and refined before generation.
    """
    candidates = sorted({score for score, _ in scores if score >= floor})
    for threshold in candidates:
        false_positives = sum(score >= threshold and not label for score, label in scores)
        if false_positives == 0:
            return threshold
    return candidates[-1] if candidates else floor


def cosine_distance(left: list[float], right: list[float]) -> float:
    dot = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    return 1 - dot / (left_norm * right_norm)


def cosine_similarity(left: list[float], right: list[float]) -> float:
    return 1 - cosine_distance(left, right)


def choose_cache_distance(pairs: list[tuple[float, bool]]) -> float:
    best: tuple[float, float] | None = None
    for threshold in sorted({distance for distance, _ in pairs}):
        tp = sum(distance <= threshold and label for distance, label in pairs)
        fp = sum(distance <= threshold and not label for distance, label in pairs)
        fn = sum(distance > threshold and label for distance, label in pairs)
        negatives = sum(not label for _, label in pairs)
        false_hit_rate = fp / negatives if negatives else 0.0
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        if false_hit_rate <= 0.01 and (best is None or (f1, -threshold) > best):
            best = (f1, -threshold)
    if best is None:
        raise RuntimeError("no cache threshold satisfies false-hit-rate constraint")
    return -best[1]


def choose_offtopic_threshold(similarities: list[float], *, quantile: float = 0.05) -> float:
    """Off-topic gate placed just below the least on-topic real query.

    Using a low quantile rather than the minimum keeps one unusual but valid
    question from widening the gate enough to let genuine off-topic input in.
    """
    if not similarities:
        raise RuntimeError("no on-topic similarities available for the off-topic gate")
    ordered = sorted(similarities)
    index = max(0, min(len(ordered) - 1, int(len(ordered) * quantile)))
    return ordered[index]


async def run(args: argparse.Namespace) -> None:
    settings = Settings()
    verify_configured_models(settings)
    golden = [
        GoldenItem.model_validate_json(line)
        for line in args.golden.read_text().splitlines()
        if line
    ]
    if len(golden) < 30:
        raise ValueError("calibration split requires at least 30 examples")

    embedder, reranker = build_embedder_and_reranker(settings)
    retriever = build_retriever(settings)
    strategies = settings.chunk_strategy_list
    strategy = strategies[0] if strategies else None

    gate_scores: list[tuple[float, bool]] = []
    answerable_vectors: list[list[float]] = []
    for item in golden:
        vector = await embedder.embed_query(item.query)
        if item.answerable:
            answerable_vectors.append(vector)
        candidates = await retriever.retrieve(
            item.query, vector, settings.retrieval_candidate_k, strategy=strategy
        )
        ranked = await reranker.rerank(item.query, candidates, settings.retrieval_candidate_k)
        gate_scores.append((ranked[0].score if ranked else float("-inf"), item.answerable))
    threshold, false_answer_rate, _ = choose_gate(gate_scores)
    confident_threshold = choose_confident_gate(gate_scores, floor=threshold)

    cache_pairs: list[tuple[float, bool]] = []
    for line in args.cache_pairs.read_text().splitlines():
        if not line:
            continue
        item = json.loads(line)
        vectors = [
            await embedder.embed_query(item["left"]),
            await embedder.embed_query(item["right"]),
        ]
        cache_pairs.append((cosine_distance(*vectors), bool(item["equivalent"])))
    if len(cache_pairs) < 30:
        raise ValueError("cache calibration requires at least 30 labeled pairs")
    cache_threshold = choose_cache_distance(cache_pairs)

    offtopic_threshold: float | None = None
    centroid, _ = load_corpus_centroid()
    if centroid and answerable_vectors:
        similarities = [cosine_similarity(vector, centroid) for vector in answerable_vectors]
        offtopic_threshold = choose_offtopic_threshold(similarities)

    embedding = embedding_fingerprint(settings)
    artifact = {
        "reranker_threshold": threshold,
        "crag_confident_threshold": confident_threshold,
        "reranker_fingerprint": reranker_fingerprint(
            settings.active_reranker_model_id,
            settings.active_reranker_revision,
            settings.active_reranker_artifact,
        ),
        "embedding_fingerprint": embedding.digest,
        "false_answer_rate": false_answer_rate,
        "sample_count": len(golden),
        "cache_distance_threshold": cache_threshold,
        "offtopic_threshold": offtopic_threshold,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(artifact, indent=2))
    print(json.dumps(artifact, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--golden", type=Path, required=True)
    parser.add_argument("--cache-pairs", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("config/calibration.json"))
    asyncio.run(run(parser.parse_args()))


if __name__ == "__main__":
    main()
