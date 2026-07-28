FROM python:3.12.11-slim-bookworm AS builder
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_CACHE_DIR=1
WORKDIR /build
COPY pyproject.toml README.md ./
COPY src ./src
RUN python -m pip wheel --wheel-dir /wheels ".[ingest]"

FROM python:3.12.11-slim-bookworm AS runtime
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
RUN groupadd --gid 10001 fastrag && useradd --uid 10001 --gid fastrag --create-home fastrag
COPY --from=builder /wheels /wheels
RUN python -m pip install --no-index --find-links=/wheels fastrag && rm -r /wheels
WORKDIR /app
COPY --chown=fastrag:fastrag config ./config
USER fastrag
EXPOSE 8000
CMD ["sh", "-c", "exec uvicorn fastrag.api:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers"]

