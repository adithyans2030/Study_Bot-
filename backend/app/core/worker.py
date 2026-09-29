"""Background ingest worker: runs one job at a time so only one document is being embedded at once
(memory is tight), while the API stays responsive."""
import asyncio
import logging
from pathlib import Path

from app.core.jobs import Job, JobQueue
from app.core.uploads import remove_upload
from app.ingest.types import IngestError
from app.okf.pipeline import run_okf
from app.rag.pipeline import StudyBot

log = logging.getLogger("studybot.worker")
DUPLICATE_NOTE = "You already had this exact file, so nothing new was added."


class JobRunner:
    def __init__(self, jobs: JobQueue, bot: StudyBot):
        self.jobs, self.bot = jobs, bot
        self._wake = asyncio.Event()
        self._loop: asyncio.AbstractEventLoop | None = None

    def notify(self) -> None:
        """Tell the worker a job was added so it starts immediately instead of on its next poll.
        Safe to call from any thread (sync endpoints run in a thread pool)."""
        if self._loop is not None and not self._loop.is_closed():
            self._loop.call_soon_threadsafe(self._wake.set)

    async def run(self) -> None:
        self._loop = asyncio.get_running_loop()
        requeued = await asyncio.to_thread(self.jobs.recover_interrupted)
        if requeued:
            log.info("re-queued %d interrupted job(s)", requeued)
        while True:
            try:
                job = await asyncio.to_thread(self.jobs.claim_next)
                if job is None:
                    try:
                        await asyncio.wait_for(self._wake.wait(), timeout=2.0)
                    except asyncio.TimeoutError:
                        pass
                    self._wake.clear()
                    continue
                await asyncio.to_thread(self.process, job)
            except asyncio.CancelledError:
                raise
            except Exception:  # never let one bad iteration kill the worker
                log.exception("worker loop error")
                await asyncio.sleep(1.0)

    def process(self, job: Job) -> None:
        uploads = self.bot.settings.uploads_dir
        result, error, unreadable = None, None, False
        try:
            result = self.bot.ingest(job.source, job.collection, job.force, title=job.title, user_id=job.user_id,
                                     progress=lambda stage: self.jobs.set_stage(job.id, stage))
        except IngestError as exc:
            error, unreadable = str(exc), True
        except Exception:
            log.exception("indexing failed for job %s", job.id)
            error = ("Something went wrong while indexing this file. It was logged; "
                     "please try again or try a different file.")

        # Everything below runs OUTSIDE the except blocks on purpose: while an exception is being
        # handled its traceback keeps a failed PDF open, and Windows cannot delete an open file.
        if error is not None:
            if unreadable and job.kind == "file":
                if job.title:  # uploads are stored under random names; show the user's own name
                    error = error.replace(Path(job.source).name, job.title)
                remove_upload(job.source, uploads)  # a file that cannot be read is not worth keeping
            self.jobs.finish(job.id, error=error)
            return

        warnings = list(result.warnings)
        if result.duplicate:
            if job.kind == "file":
                remove_upload(job.source, uploads)
            warnings.append(DUPLICATE_NOTE)
        self.jobs.finish(job.id, document_id=result.document_id, chunks=result.chunks, warnings=warnings)
        # Trigger OKF extraction in background (non-blocking)
        if result.document_id and not result.duplicate and hasattr(self, "okf_store") and self.okf_store:
            asyncio.run_coroutine_threadsafe(
                run_okf(
                    okf_store=self.okf_store,
                    embedder=self.bot.embedder,
                    ollama_url=self.bot.settings.ollama_url,
                    model=self.bot.settings.llm_model,
                    num_ctx=self.bot.settings.num_ctx,
                    full_text=getattr(result, "_full_text", ""),
                    source_title=result.title,
                    document_id=result.document_id,
                    collection_id=getattr(result, "_collection_id", 0),
                    user_id=job.user_id,
                ),
                self._loop,
            )

