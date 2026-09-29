"""Indexing job status, including a live progress stream (Server-Sent Events)."""
import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.api.deps import current_user
from app.core.accounts import User
from app.core.jobs import TERMINAL

router = APIRouter(prefix="/api/jobs", tags=["jobs"])
SSE_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}


@router.get("")
def list_jobs(request: Request, user: User = Depends(current_user)) -> list[dict]:
    return [j.public() for j in request.app.state.jobs.list_for_user(user.id)]


@router.get("/{job_id}")
def get_job(job_id: str, request: Request, user: User = Depends(current_user)) -> dict:
    job = request.app.state.jobs.get(job_id, user.id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    return job.public()


@router.get("/{job_id}/events")
async def job_events(job_id: str, request: Request, user: User = Depends(current_user)) -> StreamingResponse:
    """One event whenever the job's status or stage changes; the stream ends when it finishes."""
    jobs = request.app.state.jobs
    if await asyncio.to_thread(jobs.get, job_id, user.id) is None:
        raise HTTPException(status_code=404, detail="Job not found.")

    async def stream():
        last, idle = None, 0.0
        while True:
            job = await asyncio.to_thread(jobs.get, job_id, user.id)
            if job is None:
                return
            snapshot = (job.status, job.stage)
            if snapshot != last:
                last, idle = snapshot, 0.0
                yield f"event: job\ndata: {json.dumps(job.public())}\n\n"
            if job.status in TERMINAL:
                return
            await asyncio.sleep(0.4)
            idle += 0.4
            if idle >= 15:  # keep proxies from closing an idle stream
                idle = 0.0
                yield ": keep-alive\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream", headers=SSE_HEADERS)
