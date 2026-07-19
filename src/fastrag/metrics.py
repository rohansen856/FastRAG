from prometheus_client import Counter, Histogram

REQUESTS = Counter(
    "fastrag_queries_total", "Queries by outcome and cache status", ["outcome", "cache_status"]
)
FAILURES = Counter("fastrag_query_failures_total", "Query failures by stage", ["stage"])
LATENCY = Histogram(
    "fastrag_query_duration_seconds",
    "End-to-end query latency",
    buckets=(0.05, 0.1, 0.2, 0.4, 0.75, 1, 1.5, 2, 3, 5, 10, 20),
)
TTFT = Histogram(
    "fastrag_time_to_first_answer_chunk_seconds",
    "Time to first validated answer chunk",
    buckets=(0.05, 0.1, 0.2, 0.4, 0.75, 1, 1.5, 2, 3, 5, 10),
)
STAGE_LATENCY = Histogram(
    "fastrag_stage_duration_seconds",
    "Query component latency",
    ["stage"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.2, 0.4, 0.75, 1, 2, 5, 10),
)
