"""YouTube loader: captions via youtube-transcript-api (no API key), title via oEmbed.

Captions are cached on disk so re-ingesting works offline and a temporary YouTube block
doesn't lose data. Videos without captions are not supported yet (Whisper fallback: Phase 3).
"""
import html
import json
import re
import urllib.parse
import urllib.request
from pathlib import Path

from app.ingest.text_utils import sha256_text
from app.ingest.types import IngestError, LoadedDocument, Segment

_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")
_NOISE = re.compile(r"\[(?:music|applause|laughter)\]", re.IGNORECASE)
_LANGS = ["en", "en-US", "en-GB", "en-IN"]


def parse_video_id(url: str) -> str:
    parsed = urllib.parse.urlparse(url.strip())
    host = (parsed.hostname or "").lower().removeprefix("www.").removeprefix("m.")
    video_id = None
    if host == "youtu.be":
        video_id = parsed.path.lstrip("/").split("/")[0]
    elif host in ("youtube.com", "music.youtube.com"):
        if parsed.path == "/watch":
            video_id = urllib.parse.parse_qs(parsed.query).get("v", [None])[0]
        else:
            parts = [p for p in parsed.path.split("/") if p]
            if len(parts) >= 2 and parts[0] in ("shorts", "embed", "live", "v"):
                video_id = parts[1]
    if not video_id or not _ID.match(video_id):
        raise IngestError(f"Could not find a YouTube video id in: {url}")
    return video_id


def is_youtube_url(text: str) -> bool:
    host = (urllib.parse.urlparse(text.strip()).hostname or "").lower().removeprefix("www.").removeprefix("m.")
    return host in ("youtube.com", "music.youtube.com", "youtu.be")


def _fetch_title(video_id: str) -> str:
    url = "https://www.youtube.com/oembed?format=json&url=" + urllib.parse.quote(
        f"https://www.youtube.com/watch?v={video_id}", safe="")
    try:
        with urllib.request.urlopen(url, timeout=15) as response:
            return json.load(response).get("title") or f"YouTube video {video_id}"
    except Exception:
        return f"YouTube video {video_id}"


def _fetch_transcript(video_id: str, cache_dir: Path | None) -> dict:
    cache_file = cache_dir / "transcripts" / f"{video_id}.json" if cache_dir else None
    if cache_file and cache_file.exists():
        return json.loads(cache_file.read_text(encoding="utf-8"))

    from youtube_transcript_api import YouTubeTranscriptApi
    from youtube_transcript_api import _errors as yt_errors

    try:
        fetched = YouTubeTranscriptApi().fetch(video_id, languages=_LANGS)
    except yt_errors.TranscriptsDisabled as exc:
        raise IngestError("This video has captions turned off, so there is no transcript to read.") from exc
    except yt_errors.NoTranscriptFound as exc:
        raise IngestError("No English captions found for this video (other languages are not supported yet).") from exc
    except yt_errors.VideoUnavailable as exc:
        raise IngestError("This video is unavailable (private, removed or region-blocked).") from exc
    except (yt_errors.IpBlocked, yt_errors.RequestBlocked) as exc:
        raise IngestError("YouTube is temporarily blocking transcript requests from this network. Try again later.") from exc
    except Exception as exc:
        raise IngestError(f"Could not fetch the transcript: {exc}") from exc

    data = {
        "generated": bool(getattr(fetched, "is_generated", False)),
        "snippets": [{"text": s.text, "start": s.start, "duration": s.duration} for s in fetched.snippets],
    }
    if cache_file:
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(json.dumps(data), encoding="utf-8")
    return data


def load_youtube(url: str, cache_dir: Path | None = None) -> LoadedDocument:
    video_id = parse_video_id(url)
    data = _fetch_transcript(video_id, cache_dir)

    segments: list[Segment] = []
    for snippet in data["snippets"]:
        text = re.sub(r"\s+", " ", _NOISE.sub("", html.unescape(snippet["text"]))).strip()
        if text:
            start = float(snippet["start"])
            segments.append(Segment(text=text, t_start=start, t_end=start + float(snippet["duration"])))
    if not segments:
        raise IngestError("The transcript for this video is empty.")

    warnings = ["Auto-generated captions: names and technical terms may be misspelled."] if data.get("generated") else []
    return LoadedDocument(
        title=_fetch_title(video_id),
        source_type="youtube",
        source=f"https://www.youtube.com/watch?v={video_id}",
        content_hash=sha256_text(" ".join(s.text for s in segments)),
        segments=segments,
        warnings=warnings,
    )
