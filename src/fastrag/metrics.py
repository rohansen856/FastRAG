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
RETRIES = Counter(
    "fastrag_provider_retries_total",
    "Provider calls retried by provider and reason",
    ["provider", "reason"],
)
CIRCUIT_TRIPS = Counter(
    "fastrag_circuit_breaker_trips_total", "Circuit breaker openings by provider", ["provider"]
)
FALLBACKS = Counter(
    "fastrag_generator_fallbacks_total", "Generator fallbacks to the secondary provider", ["reason"]
)
GUARDRAIL_BLOCKS = Counter(
    "fastrag_guardrail_blocks_total", "Requests refused by an input guardrail", ["rule"]
)
CRAG_ACTIONS = Counter("fastrag_crag_actions_total", "CRAG corrective actions taken", ["action"])
