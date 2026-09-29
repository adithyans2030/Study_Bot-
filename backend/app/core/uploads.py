"""Safe handling of uploaded files.

Never trust the filename or Content-Type a browser sends: the file's real type is decided from
its contents, it is stored under a random name, and only the sanitised original name is kept as a
display title.
"""
import gc
import logging
import re
import time
import uuid
import zipfile
from pathlib import Path
from typing import Protocol

from app.ingest.text_utils import prettify_stem

log = logging.getLogger("studybot.uploads")

CHUNK = 1024 * 1024
MAX_UNCOMPRESSED_BYTES = 400 * 1024 * 1024  # guards Office files (zip archives) against zip bombs
MAX_ZIP_ENTRIES = 20_000
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")


class UploadError(Exception):
    """The upload was rejected. `status` is the HTTP status; the message is safe to show."""

    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


class AsyncReader(Protocol):
    async def read(self, size: int = -1) -> bytes: ...


def display_title(filename: str | None) -> str:
    """A safe, readable title from a browser-supplied filename."""
    name = _CONTROL.sub("", (filename or "").replace("\\", "/")).split("/")[-1].strip()
    title = prettify_stem(name) if name else ""
    return (title or "Untitled")[:120]


def sniff_kind(path: Path) -> str:
    """Return 'pdf', 'pptx' or 'docx' from the file's contents, or raise UploadError."""
    with open(path, "rb") as handle:
        head = handle.read(1024)
    if b"%PDF-" in head:
        return "pdf"
    if head.startswith(b"PK\x03\x04"):
        try:
            with zipfile.ZipFile(path) as archive:
                entries = archive.infolist()
                if len(entries) > MAX_ZIP_ENTRIES or sum(e.file_size for e in entries) > MAX_UNCOMPRESSED_BYTES:
                    raise UploadError("This file expands to an unreasonable size and was rejected.")
                names = {e.filename for e in entries}
        except zipfile.BadZipFile as exc:
            raise UploadError("This file is damaged and could not be opened.") from exc
        if "ppt/presentation.xml" in names:
            return "pptx"
        if "word/document.xml" in names:
            return "docx"
        raise UploadError("This is a ZIP file, not a PowerPoint (.pptx) or Word (.docx) document.")
    if head.startswith(b"\xd0\xcf\x11\xe0"):
        raise UploadError("Old .doc / .ppt files are not supported. Re-save it as .docx / .pptx and upload again.")
    raise UploadError("Unsupported file. Upload a PDF, PowerPoint (.pptx) or Word (.docx) file.", 415)


async def save_upload(upload: AsyncReader, directory: Path, max_bytes: int) -> tuple[Path, str]:
    """Stream an upload to `directory` under a random name, enforcing the size limit while
    writing, then verify its type. Returns (final path, kind). Leaves nothing behind on failure."""
    directory.mkdir(parents=True, exist_ok=True)
    partial = directory / f"{uuid.uuid4().hex}.part"
    try:
        written = 0
        with open(partial, "wb") as out:
            while True:
                block = await upload.read(CHUNK)
                if not block:
                    break
                written += len(block)
                if written > max_bytes:
                    raise UploadError(f"File is too large (limit {max_bytes // (1024 * 1024)} MB).", 413)
                out.write(block)
        if written == 0:
            raise UploadError("The file is empty.")
        kind = sniff_kind(partial)
        final = partial.with_suffix(f".{kind}")
        partial.replace(final)
        return final, kind
    except BaseException:
        partial.unlink(missing_ok=True)
        raise


def remove_upload(source: str, uploads_dir: Path) -> bool:
    """Delete a stored upload, but only if `source` really lives inside the uploads directory.

    On Windows a file still held open by a library cannot be deleted, so a few short retries
    (with a garbage collection to release lingering handles) are made before giving up."""
    try:
        path, root = Path(source).resolve(), uploads_dir.resolve()
        if not (path.is_file() and path.is_relative_to(root)):
            return False
    except (OSError, ValueError):
        return False
    for attempt in range(5):
        try:
            path.unlink()
            return True
        except FileNotFoundError:
            return True
        except OSError:
            gc.collect()
            time.sleep(0.05 * (attempt + 1))
    log.warning("could not delete uploaded file %s", path.name)
    return False
