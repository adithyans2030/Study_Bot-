"""Shared helpers for the evaluation scripts."""
import json
import os
from pathlib import Path

from app.config import Settings, default_home
from app.rag.pipeline import StudyBot
from app.rag.store import ChunkRecord, Store

HERE = Path(__file__).parent
GOLDEN = HERE / "golden.jsonl"
CORPUS_SPEC = HERE / "corpus.json"


def load_golden(path: Path = GOLDEN) -> list[dict]:
    with open(path, encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def default_corpus_dir() -> Path:
    return default_home() / "eval_corpus"


def is_relevant(chunk: ChunkRecord, expect: list[dict]) -> bool:
    """A chunk is relevant if it comes from an expected document AND overlaps the expected
    pages (PDF) or time window in seconds (YouTube)."""
    for target in expect:
        if target["doc"] not in chunk.source:
            continue
        if "pages" in target:
            start, end = chunk.meta.get("page_start"), chunk.meta.get("page_end")
            if start is not None and any(start <= page <= end for page in target["pages"]):
                return True
        elif "t" in target:
            t0, t1 = target["t"]
            if chunk.meta.get("t_start", 1e18) < t1 and chunk.meta.get("t_end", -1) > t0:
                return True
        else:
            return True
    return False


def keywords_ok(answer: str, kw: list[str]) -> bool:
    """Every entry must match; an entry like 'a|b' matches if any alternative appears."""
    text = answer.lower()
    return all(any(alt.strip().lower() in text for alt in entry.split("|")) for entry in kw)


def build_bot(db_name: str, **settings_overrides) -> StudyBot:
    """A StudyBot on a dedicated evaluation database, never the user's real index."""
    settings = Settings(_env_file=None, **settings_overrides)
    settings.ensure_dirs()
    (settings.home / "eval").mkdir(parents=True, exist_ok=True)
    store = Store(settings.home / "eval" / db_name)
    return StudyBot(settings, store=store)


def ingest_corpus(bot: StudyBot, corpus_dir: Path, log=print, force: bool = False) -> None:
    """Index the corpus. Unchanged sources are skipped unless force=True (needed after a loader or
    chunker change, because the source file itself has not changed)."""
    spec = json.loads(CORPUS_SPEC.read_text(encoding="utf-8"))
    for collection, sources in spec.items():
        for name in sources.get("files", []):
            path = corpus_dir / name
            if not path.exists():
                raise SystemExit(f"Missing corpus file: {path}. Put your PDFs in {corpus_dir}.")
            result = bot.ingest(str(path), collection, force=force)
            log(f"  {'kept   ' if result.skipped else 'indexed'} {result.title} -> {result.chunks} chunks")
        for url in sources.get("youtube", []):
            result = bot.ingest(url, collection, force=force)
            log(f"  {'kept   ' if result.skipped else 'indexed'} {result.title[:60]} -> {result.chunks} chunks")


def env_home_note() -> str:
    return os.environ.get("STUDYBOT_HOME") or str(default_home())
