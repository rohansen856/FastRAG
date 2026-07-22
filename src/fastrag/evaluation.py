from __future__ import annotations

import argparse
import asyncio
import json
import statistics
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
from pydantic import BaseModel, Field, model_validator

from .adapters.embedding import FastEmbedder
from .adapters.retrieval import FastEmbedReranker, QdrantHybridRetriever
from .config import Settings
from .model_artifacts import verify_configured_models


class GoldenItem(BaseModel):
    id: str
    query: str = Field(min_length=1)
    reference_answer: str | None
    answerable: bool
    relevant_chunk_ids: list[str] = Field(default_factory=list)
    reference_contexts: list[str] = Field(default_factory=list)
    category: str

    @model_validator(mode="after")
    def validate_labels(self) -> GoldenItem:
        if self.answerable and (not self.reference_answer or not self.relevant_chunk_ids):
            raise ValueError("answerable items require an answer and relevant chunks")
        if not self.answerable and self.reference_answer is not None:
            raise ValueError("unanswerable items must use a null reference_answer")
        return self


@dataclass(slots=True)
class EvaluationRecord:
    item: GoldenItem
    response: dict[str, Any]
    retrieved_ids: list[str]
    reranked_ids: list[str]
    retrieved_contexts: list[str]


def load_golden(path: Path, *, minimum_items: int = 200) -> list[GoldenItem]:
    items = [GoldenItem.model_validate_json(line) for line in path.read_text().splitlines() if line]
    if len(items) < minimum_items:
        raise ValueError(
            f"golden dataset has {len(items)} items; at least {minimum_items} required"
        )
    ids = [item.id for item in items]
    if len(ids) != len(set(ids)):
        raise ValueError("golden item IDs must be unique")
    no_answer_fraction = sum(not item.answerable for item in items) / len(items)
    if no_answer_fraction < 0.25:
        raise ValueError("at least 25% of golden items must be unanswerable")
    return items


async def collect_records(
    items: list[GoldenItem], settings: Settings, api_url: str
) -> list[EvaluationRecord]:
    verify_configured_models(settings)
    embedder = FastEmbedder(
        settings.dense_model_id,
        query_prefix=settings.dense_query_prefix,
        normalize=settings.dense_normalize,
        model_path=settings.dense_model_path,
    )
    retriever = QdrantHybridRetriever(
        settings.qdrant_url,
        settings.qdrant_alias,
        api_key=(settings.qdrant_api_key.get_secret_value() if settings.qdrant_api_key else None),
    )
    reranker = FastEmbedReranker(
        settings.reranker_model_id, model_path=settings.reranker_model_path
    )
    records: list[EvaluationRecord] = []
    headers = {"Authorization": f"Bearer {settings.query_api_key.get_secret_value()}"}
    async with httpx.AsyncClient(timeout=60) as client:
        for item in items:
            vector = await embedder.embed_query(item.query)
            candidates = await retriever.retrieve(
                item.query, vector, settings.retrieval_candidate_k
            )
            reranked = await reranker.rerank(item.query, candidates, settings.retrieval_candidate_k)
            response = await client.post(
                f"{api_url.rstrip('/')}/v1/query",
                headers=headers,
                json={"query": item.query},
            )
            response.raise_for_status()
            records.append(
                EvaluationRecord(
                    item=item,
                    response=response.json(),
                    retrieved_ids=[chunk.chunk_id for chunk in candidates],
                    reranked_ids=[entry.chunk.chunk_id for entry in reranked],
                    retrieved_contexts=[
                        entry.chunk.text for entry in reranked[: settings.context_top_k]
                    ],
                )
            )
    return records


def deterministic_metrics(records: list[EvaluationRecord]) -> dict[str, float]:
    answerable = [record for record in records if record.item.answerable]
    unanswerable = [record for record in records if not record.item.answerable]
    recalls: list[float] = []
    reciprocal_ranks: list[float] = []
    valid_citations: list[float] = []
    for record in answerable:
        relevant = set(record.item.relevant_chunk_ids)
        recalls.append(len(relevant.intersection(record.retrieved_ids)) / len(relevant))
        rank = next(
            (
                index
                for index, chunk_id in enumerate(record.reranked_ids[:5], 1)
                if chunk_id in relevant
            ),
            None,
        )
        reciprocal_ranks.append(1 / rank if rank else 0)
        citation_ids = {item["chunk_id"] for item in record.response["citations"]}
        valid_citations.append(float(citation_ids.issubset(set(record.reranked_ids[:5]))))
    false_answers = sum(record.response["outcome"] == "answered" for record in unanswerable)
    return {
        "recall_at_20": statistics.fmean(recalls),
        "mrr_at_5": statistics.fmean(reciprocal_ranks),
        "valid_citation_rate": statistics.fmean(valid_citations),
        "false_answer_rate": false_answers / len(unanswerable),
    }


def ragas_metrics(records: list[EvaluationRecord], settings: Settings) -> dict[str, float]:
    from fastembed import TextEmbedding
    from langchain_core.embeddings import Embeddings
    from langchain_openai import ChatOpenAI
    from ragas import EvaluationDataset, evaluate
    from ragas.embeddings import LangchainEmbeddingsWrapper
    from ragas.llms import LangchainLLMWrapper
    from ragas.metrics import FactualCorrectness, Faithfulness, ResponseRelevancy

    if settings.dense_model_path is None:
        raise RuntimeError("golden evaluation requires a verified local embedding model")

    dataset = EvaluationDataset.from_list(
        [
            {
                "user_input": record.item.query,
                "retrieved_contexts": record.retrieved_contexts,
                "response": record.response["answer"],
                "reference": record.item.reference_answer
                or "The sources do not contain the answer.",
            }
            for record in records
        ]
    )
    judge = ChatOpenAI(
        model=settings.llm_model,
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
        temperature=0,
    )

    class EvaluationEmbeddings(Embeddings):  # type: ignore[misc]
        def __init__(self) -> None:
            self._model = TextEmbedding(
                model_name=settings.dense_model_id,
                specific_model_path=str(settings.dense_model_path),
                local_files_only=True,
            )

        def embed_documents(self, texts: list[str]) -> list[list[float]]:
            return [[float(value) for value in vector] for vector in self._model.embed(texts)]

        def embed_query(self, text: str) -> list[float]:
            vector = next(iter(self._model.query_embed(settings.dense_query_prefix + text)))
            return [float(value) for value in vector]

    result = evaluate(
        dataset=dataset,
        metrics=[Faithfulness(), ResponseRelevancy(), FactualCorrectness()],
        llm=LangchainLLMWrapper(judge),
        embeddings=LangchainEmbeddingsWrapper(EvaluationEmbeddings()),
        raise_exceptions=True,
        show_progress=False,
    )
    frame = result.to_pandas()
    return {
        "faithfulness": float(frame["faithfulness"].mean()),
        "response_relevancy": float(frame["answer_relevancy"].mean()),
        "answer_correctness": float(frame["factual_correctness"].mean()),
    }


THRESHOLDS = {
    "recall_at_20": 0.95,
    "mrr_at_5": 0.85,
    "faithfulness": 0.90,
    "response_relevancy": 0.90,
    "answer_correctness": 0.90,
    "valid_citation_rate": 1.0,
}


def check_thresholds(metrics: dict[str, float]) -> list[str]:
    failures = [
        f"{name}={metrics.get(name, float('nan')):.4f} < {threshold:.4f}"
        for name, threshold in THRESHOLDS.items()
        if metrics.get(name, float("-inf")) < threshold
    ]
    if metrics.get("false_answer_rate", 1.0) > 0.05:
        failures.append(f"false_answer_rate={metrics['false_answer_rate']:.4f} > 0.0500")
    return failures


async def async_main(args: argparse.Namespace) -> int:
    settings = Settings()
    items = load_golden(args.dataset, minimum_items=args.minimum_items)
    records = await collect_records(items, settings, args.api_url)
    metrics = deterministic_metrics(records)
    metrics.update(await asyncio.to_thread(ragas_metrics, records, settings))
    failures = check_thresholds(metrics)
    report = {
        "metrics": metrics,
        "num_samples": len(records),
        "passed": not failures,
        "failed_thresholds": failures,
        "records": [
            {
                "id": record.item.id,
                "response": record.response,
                "retrieved_ids": record.retrieved_ids,
                "reranked_ids": record.reranked_ids,
            }
            for record in records
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2))
    print(json.dumps({key: value for key, value in report.items() if key != "records"}, indent=2))
    return 0 if not failures else 1


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--api-url", default="http://localhost:8000")
    parser.add_argument("--output", type=Path, default=Path("eval/results/report.json"))
    parser.add_argument("--minimum-items", type=int, default=200)
    raise SystemExit(asyncio.run(async_main(parser.parse_args())))


if __name__ == "__main__":
    main()
