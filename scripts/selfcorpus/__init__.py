"""Helpers for building FastRAG's corpus out of FastRAG's own repository.

Kept beside `scripts/ingest-self.py` rather than inside `src/fastrag/` because
none of it runs in the request path: it is corpus construction, like
`scripts/ingest-msmarco.py`, not service code.
"""
