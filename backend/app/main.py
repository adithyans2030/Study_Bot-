"""FastAPI application factory. Run with: uvicorn app.main:create_app --factory"""
import asyncio
import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.api import auth, chat, conversations, health, jobs, library, voice, study
from app.okf import routes as okf_routes
from app.okf.store import OKFStore
from app.config import Settings
from app.core import security
from app.core.accounts import Accounts, LoginLimiter
from app.core.conversations import Conversations
from app.core.jobs import JobQueue
from app.core.logging_setup import configure_logging
from app.core.ollama import chat_stream
from app.core.worker import JobRunner
from app.rag.pipeline import StudyBot
from app.voice.stt import Transcriber

logger = logging.getLogger("studybot")
# The React dashboard's build output (see studybot/frontend/vite.config.ts â€” `npm run build`
# writes here; not committed, like any other build artifact). The plain-JS dashboard this replaced
# lived in app/static/, kept on disk for now as a reference but no longer served by anything below.
DIST_DIR = Path(__file__).parent / "dist"


class NoCacheStatic(StaticFiles):
    """The app shell changes with releases; always revalidate so a browser never runs stale JS."""

    async def get_response(self, path, scope):
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = "no-cache"
        return response


class ImmutableStatic(StaticFiles):
    """Vite content-hashes every filename under /assets (e.g. index-B8bIP7Qg.js) â€” a new release
    means a new URL, so the old one can be cached as hard as a browser will allow."""

    async def get_response(self, path, scope):
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return response


async def _warm_up(app: FastAPI, bot: StudyBot, settings: Settings, transcriber: Transcriber | None) -> None:
    """Load the embedding model and the LLM in the background so the first question is not slow.
    A failure is remembered so /api/ready can say why indexing will not work."""
    try:
        warm = getattr(bot.embedder, "warm", None)
        if warm:
            await asyncio.to_thread(warm)
        app.state.embedder_error = None
    except Exception as exc:
        logger.warning("embedding model warm-up failed", exc_info=True)
        app.state.embedder_error = str(exc)[:200]
    if transcriber is not None:  # downloads the speech model on the very first start (~150 MB)
        try:
            await asyncio.to_thread(transcriber.warm)
            app.state.stt_error = None
        except Exception as exc:
            logger.warning("speech model warm-up failed: %s", exc)
            app.state.stt_error = str(exc)[:200]
    try:
        async for _ in chat_stream(settings.ollama_url, settings.llm_model,
                                   [{"role": "user", "content": "Reply with OK."}],
                                   num_ctx=settings.num_ctx, num_predict=4):
            pass
    except Exception as exc:
        logger.warning("LLM warm-up skipped: %s", exc)


def create_app(settings: Settings | None = None, bot: StudyBot | None = None,
               transcriber: Transcriber | None = None) -> FastAPI:
    settings = settings or Settings()
    configure_logging(settings)
    bot = bot or StudyBot(settings)
    if transcriber is None and settings.voice_enabled:
        transcriber = Transcriber(settings.stt_model, settings.models_dir, settings.stt_threads)
    accounts = Accounts(bot.store, settings.session_days)
    queue = JobQueue(bot.store)
    runner = JobRunner(queue, bot)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        settings.ensure_dirs()
        logger.info("StudyBot %s starting; data home: %s", __version__, settings.home)
        tasks = [asyncio.create_task(runner.run(), name="job-runner")]
        if settings.warm_on_start:
            tasks.append(asyncio.create_task(_warm_up(app, bot, settings, transcriber), name="warm-up"))
        try:
            yield
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

    app = FastAPI(title="StudyBot", version=__version__, lifespan=lifespan)
    app.state.settings = settings
    app.state.bot = bot
    app.state.store = bot.store
    app.state.accounts = accounts
    app.state.jobs = queue
    app.state.conversations = Conversations(bot.store)
    app.state.runner = runner
    okf_store = OKFStore(bot.store)
    app.state.okf_store = okf_store
    runner.okf_store = okf_store
    app.state.limiter = LoginLimiter(settings.login_max_failures)
    app.state.embedder_error = None
    app.state.transcriber = transcriber
    app.state.stt_error = None
    app.state.started_at = time.monotonic()

    security.install(app, settings)
    for router in (health.router, auth.router, library.router, jobs.router, chat.router, conversations.router,
                   voice.router, okf_routes.router, study.router):
        app.include_router(router)

    @app.get("/manifest.webmanifest", include_in_schema=False)
    def manifest() -> FileResponse:
        path = DIST_DIR / "manifest.webmanifest"
        if not path.is_file():
            raise HTTPException(404, "frontend not built â€” run `npm run build` in studybot/frontend")
        return FileResponse(path, media_type="application/manifest+json",
                            headers={"Cache-Control": "no-cache"})

    @app.get("/sw.js", include_in_schema=False)
    def service_worker() -> FileResponse:
        # Served from the site root so its scope covers the whole app; never cached so updates apply.
        path = DIST_DIR / "sw.js"
        if not path.is_file():
            raise HTTPException(404, "frontend not built â€” run `npm run build` in studybot/frontend")
        return FileResponse(path, media_type="text/javascript", headers={"Cache-Control": "no-cache"})

    if DIST_DIR.is_dir():
        app.mount("/assets", ImmutableStatic(directory=DIST_DIR / "assets"), name="assets")
        app.mount("/icons", NoCacheStatic(directory=DIST_DIR / "icons"), name="icons")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str) -> FileResponse:
        """Every route React Router owns (/login, /app, /app/chat/abc, ...) â€” and any other
        root-level file Vite emits whose name isn't fixed enough for its own route above (the
        content-hashed workbox-*.js runtime, favicon.svg, registerSW.js) â€” gets this same
        catch-all, registered last so it never shadows /api/* or the routes above it."""
        # full_path comes straight from the URL; resolve it and check it's still inside DIST_DIR
        # before treating it as a real file â€” otherwise "/..%2f..%2fapp%2fconfig.py" would just
        # work. Anything outside (or missing) falls back to index.html, same as any other
        # not-a-real-file path here, rather than a 403/404 that would leak which check failed.
        candidate = (DIST_DIR / full_path).resolve()
        if full_path and candidate.is_relative_to(DIST_DIR) and candidate.is_file():
            return FileResponse(candidate, headers={"Cache-Control": "no-cache"})
        index = DIST_DIR / "index.html"
        if not index.is_file():
            raise HTTPException(404, "frontend not built â€” run `npm run build` in studybot/frontend")
        return FileResponse(index, headers={"Cache-Control": "no-cache"})

    return app


