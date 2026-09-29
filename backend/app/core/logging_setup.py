"""File logging for when the server runs detached (Task Scheduler, no console attached).

Uvicorn already prints its own request log to the console; `scripts\\run.ps1` redirects that whole
console to a dated file. This adds a rotating file for the app's own messages (warm-up, ingest and
chat errors) so they survive even if the console redirect is not in use (e.g. `run_dev.ps1`).
"""
import logging
from logging.handlers import RotatingFileHandler

from app.config import Settings

FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


def configure_logging(settings: Settings) -> None:
    """Point the "studybot" logger at `settings.logs_dir`. Safe to call once per real start-up and,
    for tests, once per `create_app()` with a fresh temp home each time: re-pointing (rather than
    a one-shot "already configured" guard) avoids leaving a handler open on a directory a previous
    test already deleted."""
    settings.ensure_dirs()
    target = str(settings.logs_dir / "studybot.log")
    logger = logging.getLogger("studybot")
    if getattr(logger, "_studybot_log_target", None) == target:
        return
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
        handler.close()

    logger.setLevel(logging.INFO)
    formatter = logging.Formatter(FORMAT)

    file_handler = RotatingFileHandler(target, maxBytes=5_000_000, backupCount=5, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    console = logging.StreamHandler()
    console.setFormatter(formatter)
    logger.addHandler(console)
    logger._studybot_log_target = target
