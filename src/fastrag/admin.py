from __future__ import annotations

import re
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from redis import Redis
from rq import Queue
from rq.job import Job

from .config import Settings
from .jobs import SUPPORTED_SUFFIXES, rebuild_documents

DOCUMENT_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")


def create_admin_router(settings: Settings, authorization: Any) -> APIRouter:
    router = APIRouter(
        prefix="/v1/admin",
        tags=["administration"],
        dependencies=[Depends(authorization)],
    )

    def queue() -> Queue:
        return Queue("ingestion", connection=Redis.from_url(settings.redis_url))

    @router.post("/documents", status_code=status.HTTP_202_ACCEPTED)
    async def upload_document(
        document_id: Annotated[str, Form()], file: Annotated[UploadFile, File()]
    ) -> dict[str, str]:
        _validate_document_id(document_id)
        suffix = Path(file.filename or "").suffix.casefold()
        if suffix not in SUPPORTED_SUFFIXES:
            raise HTTPException(status_code=415, detail="supported types: PDF, Markdown, text")
        target_dir = settings.data_dir / "documents"
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / f"{document_id}{suffix}"
        temporary = target.with_suffix(f"{suffix}.upload")
        size = 0
        with temporary.open("wb") as output:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > 100 * 1024 * 1024:
                    temporary.unlink(missing_ok=True)
                    raise HTTPException(status_code=413, detail="document exceeds 100 MiB")
                output.write(chunk)
        temporary.replace(target)
        job = queue().enqueue(rebuild_documents, job_timeout="2h", result_ttl=604_800)
        return {"document_id": document_id, "job_id": job.id}

    @router.delete("/documents/{document_id}", status_code=status.HTTP_202_ACCEPTED)
    async def delete_document(document_id: str) -> dict[str, str]:
        _validate_document_id(document_id)
        matches = list((settings.data_dir / "documents").glob(f"{document_id}.*"))
        if not matches:
            raise HTTPException(status_code=404, detail="document not found")
        for path in matches:
            if path.is_file() and path.suffix.casefold() in SUPPORTED_SUFFIXES:
                path.unlink()
        job = queue().enqueue(rebuild_documents, job_timeout="2h", result_ttl=604_800)
        return {"document_id": document_id, "job_id": job.id}

    @router.post("/indexes/rebuild", status_code=status.HTTP_202_ACCEPTED)
    async def rebuild() -> dict[str, str]:
        job = queue().enqueue(rebuild_documents, job_timeout="2h", result_ttl=604_800)
        return {"job_id": job.id}

    @router.get("/jobs/{job_id}")
    async def job_status(job_id: str) -> dict[str, Any]:
        try:
            job = Job.fetch(job_id, connection=queue().connection)
        except Exception as exc:
            raise HTTPException(status_code=404, detail="job not found") from exc
        return {
            "job_id": job.id,
            "status": job.get_status(refresh=True),
            "result": job.result if job.is_finished else None,
            "error": job.exc_info[-2_000:] if job.is_failed and job.exc_info else None,
        }

    return router


def _validate_document_id(document_id: str) -> None:
    if not DOCUMENT_ID_RE.fullmatch(document_id):
        raise HTTPException(status_code=422, detail="invalid document_id")
