"""Accepting a browser recording safely.

The decoder (FFmpeg, inside PyAV) understands hundreds of formats, and parsing hostile files is a
classic attack surface. So only the handful of containers browsers actually record are accepted,
decided from the file's first bytes, never from its name or Content-Type.
"""
import gc
import logging
import time
import uuid
from pathlib import Path

from app.core.uploads import AsyncReader, UploadError

log = logging.getLogger("studybot.voice")
CHUNK = 256 * 1024


def sniff_audio(head: bytes) -> str | None:
    """'webm' | 'ogg' | 'wav' | 'mp4' | 'mp3' | 'flac', or None if it is not a browser-recordable format."""
    if head.startswith(b"\x1a\x45\xdf\xa3"):
        return "webm"  # Chrome, Edge, Firefox (MediaRecorder default)
    if head.startswith(b"OggS"):
        return "ogg"
    if head[:4] == b"RIFF" and head[8:12] == b"WAVE":
        return "wav"
    if head[4:8] == b"ftyp":
        return "mp4"  # Safari / iOS
    if head.startswith(b"ID3") or (len(head) > 1 and head[0] == 0xFF and (head[1] & 0xE0) == 0xE0):
        return "mp3"
    if head.startswith(b"fLaC"):
        return "flac"
    return None


async def save_recording(upload: AsyncReader, directory: Path, max_bytes: int) -> Path:
    """Stream a recording to a temporary file, enforcing the size limit and the container check.
    The caller must delete the file (see `discard`)."""
    directory.mkdir(parents=True, exist_ok=True)
    kind_less = directory / f"{uuid.uuid4().hex}.rec"
    try:
        written, head = 0, b""
        with open(kind_less, "wb") as out:
            while True:
                block = await upload.read(CHUNK)
                if not block:
                    break
                if written == 0:
                    head = block[:16]
                written += len(block)
                if written > max_bytes:
                    raise UploadError(f"That recording is too large (limit {max_bytes // (1024 * 1024)} MB).", 413)
                out.write(block)
        if written == 0:
            raise UploadError("The recording is empty.")
        kind = sniff_audio(head)
        if kind is None:
            raise UploadError("That does not look like an audio recording.", 415)
        final = kind_less.with_suffix(f".{kind}")
        kind_less.replace(final)
        return final
    except BaseException:
        kind_less.unlink(missing_ok=True)
        raise


def discard(path: Path) -> None:
    """Delete a temporary recording. Windows cannot delete a file the decoder still holds, so retry briefly."""
    for attempt in range(6):
        try:
            path.unlink(missing_ok=True)
            return
        except OSError:
            gc.collect()
            time.sleep(0.05 * (attempt + 1))
    log.warning("could not delete temporary recording %s", path.name)
