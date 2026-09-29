"""Pick the right loader for a file path or URL."""
from pathlib import Path

from app.ingest.docx_loader import load_docx
from app.ingest.pdf_loader import load_pdf
from app.ingest.pptx_loader import load_pptx
from app.ingest.types import IngestError, LoadedDocument
from app.ingest.youtube_loader import is_youtube_url, load_youtube

SUPPORTED = ".pdf, .pptx, .docx or a YouTube link"
_FILE_LOADERS = {".pdf": load_pdf, ".pptx": load_pptx, ".docx": load_docx}
_LEGACY = {".ppt": ".pptx", ".doc": ".docx"}


def load_source(source: str, cache_dir: Path | None = None) -> LoadedDocument:
    if source.lower().startswith(("http://", "https://")):
        if is_youtube_url(source):
            return load_youtube(source, cache_dir)
        raise IngestError(f"Only YouTube links are supported for web sources right now (got: {source}).")

    path = Path(source).expanduser()
    if not path.is_file():
        raise IngestError(f"File not found: {source}")
    suffix = path.suffix.lower()
    if suffix in _LEGACY:
        raise IngestError(f"Old {suffix} files are not supported. Re-save '{path.name}' as {_LEGACY[suffix]} and try again.")
    loader = _FILE_LOADERS.get(suffix)
    if loader is None:
        raise IngestError(f"Unsupported file type '{suffix}'. Supported: {SUPPORTED}.")
    return loader(path)
