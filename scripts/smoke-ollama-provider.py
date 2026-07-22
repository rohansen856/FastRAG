#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio

from fastrag.adapters.generation import OpenAICompatibleGenerator
from fastrag.domain import Chunk


async def run(args: argparse.Namespace) -> int:
    generator = OpenAICompatibleGenerator(
        base_url=args.base_url,
        api_key=args.api_key,
        model=args.model,
        system_prompt=(
            "Answer only from the supplied source. Cite the source with its exact "
            '[C:chunk-id] marker. If the source is insufficient, say "I don\'t know".'
        ),
        max_tokens=80,
        timeout_seconds=args.timeout,
    )
    chunk = Chunk(
        chunk_id="smoke-1",
        document_id="smoke-doc",
        text="FastRAG smoke test answer: the local provider is reachable.",
        title="Smoke",
        source_uri="local-smoke",
    )
    answer = ""
    async for piece in generator.stream("What does the smoke test prove?", [chunk]):
        answer += piece
    print(answer.strip())
    if "reachable" not in answer.lower() or "[C:smoke-1]" not in answer:
        print("Smoke test failed: response did not include expected grounded citation.")
        return 1
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Smoke-test Ollama through FastRAG's LLM adapter")
    parser.add_argument("--base-url", default="http://127.0.0.1:11434/v1")
    parser.add_argument("--api-key", default="ollama")
    parser.add_argument("--model", default="llama3.2:latest")
    parser.add_argument("--timeout", type=float, default=30.0)
    raise SystemExit(asyncio.run(run(parser.parse_args())))


if __name__ == "__main__":
    main()
