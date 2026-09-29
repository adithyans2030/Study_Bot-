"""Speech input: turn a browser recording into text. The text then goes through the normal chat path."""
import asyncio
import logging

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile

from app.api.deps import current_user
from app.core.accounts import User
from app.core.uploads import UploadError
from app.voice.audio import discard, save_recording
from app.voice.stt import AudioTooLong, SpeechUnavailable

router = APIRouter(prefix="/api/voice", tags=["voice"])
log = logging.getLogger("studybot.voice")


@router.get("/status")
def status(request: Request, user: User = Depends(current_user)) -> dict:
    """Whether the microphone button can work: the recogniser is installed and its model has loaded."""
    state = request.app.state
    transcriber = state.transcriber
    error = getattr(state, "stt_error", None)
    return {"available": error is None, "ready": transcriber is not None and transcriber.loaded,
            "model": transcriber.model_name if transcriber is not None else None, "error": error}


@router.post("/transcribe")
async def transcribe(request: Request, audio: UploadFile = File(...), user: User = Depends(current_user)) -> dict:
    state = request.app.state
    settings, transcriber = state.settings, state.transcriber
    if transcriber is None:
        raise HTTPException(status_code=503, detail="Speech recognition is turned off on this server.")
    limit = settings.max_audio_mb * 1024 * 1024
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > limit + 64 * 1024:
        raise HTTPException(status_code=413, detail=f"That recording is too large (limit {settings.max_audio_mb} MB).")
    try:
        path = await save_recording(audio, settings.cache_dir / "voice", limit)
    except UploadError as exc:
        raise HTTPException(status_code=exc.status, detail=str(exc)) from exc
    try:
        result = await asyncio.to_thread(transcriber.transcribe, path, settings.max_audio_seconds)
    except AudioTooLong as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc
    except SpeechUnavailable as exc:
        state.stt_error = str(exc)
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        discard(path)  # after the decoder is done with it; the audio is never kept
    return {"text": result.text, "audio_seconds": round(result.audio_seconds, 1), "seconds": round(result.seconds, 1)}
