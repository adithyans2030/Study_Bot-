"""Liveness (/api/health) and readiness (/api/ready) endpoints."""
import tempfile
import time

from fastapi import APIRouter, Request, Response

from app import __version__
from app.core.ollama import list_models, normalize_model_name

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
def health(request: Request) -> dict:
    """Liveness only: the process is up. Never touches dependencies."""
    return {
        "status": "ok",
        "version": __version__,
        "uptime_seconds": round(time.monotonic() - request.app.state.started_at, 1),
    }


@router.get("/ready")
async def ready(request: Request, response: Response) -> dict:
    """Readiness: data dir writable, Ollama reachable, configured LLM pulled. 503 if any fails."""
    settings = request.app.state.settings
    checks: dict[str, dict] = {}

    try:
        with tempfile.NamedTemporaryFile(dir=settings.home):
            pass
        checks["data_dir"] = {"ok": True, "detail": str(settings.home)}
    except OSError as exc:
        checks["data_dir"] = {"ok": False, "detail": f"not writable: {exc}"}

    embedder_error = getattr(request.app.state, "embedder_error", None)
    checks["embedding_model"] = ({"ok": False, "detail": f"could not load: {embedder_error}"} if embedder_error
                                 else {"ok": True, "detail": settings.embed_model})

    try:
        models = await list_models(settings.ollama_url)
        checks["ollama"] = {"ok": True, "detail": f"{len(models)} model(s) available"}
        wanted = normalize_model_name(settings.llm_model)
        if wanted in models:
            checks["llm_model"] = {"ok": True, "detail": wanted}
        else:
            checks["llm_model"] = {"ok": False, "detail": f"'{wanted}' not pulled; run: ollama pull {settings.llm_model}"}
    except Exception as exc:
        checks["ollama"] = {"ok": False, "detail": f"unreachable at {settings.ollama_url}: {exc}"}
        checks["llm_model"] = {"ok": False, "detail": "skipped: Ollama unreachable"}

    all_ok = all(check["ok"] for check in checks.values())
    if not all_ok:
        response.status_code = 503
    return {"ready": all_ok, "checks": checks}
