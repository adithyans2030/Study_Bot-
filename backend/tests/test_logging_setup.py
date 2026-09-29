import logging

from app.core.logging_setup import configure_logging


def test_log_file_is_created_and_receives_messages(settings):
    configure_logging(settings)
    logging.getLogger("studybot").info("hello from a test")
    for handler in logging.getLogger("studybot").handlers:
        handler.flush()

    log_file = settings.logs_dir / "studybot.log"
    assert log_file.exists()
    assert "hello from a test" in log_file.read_text(encoding="utf-8")


def test_reconfiguring_for_a_new_home_does_not_write_to_the_old_one(settings, tmp_path):
    from app.config import Settings

    configure_logging(settings)
    old_log = settings.logs_dir / "studybot.log"

    other = Settings(home=tmp_path / "Other", warm_on_start=False, _env_file=None)
    configure_logging(other)
    logging.getLogger("studybot").info("goes to the new home only")
    for handler in logging.getLogger("studybot").handlers:
        handler.flush()

    assert "goes to the new home only" in (other.logs_dir / "studybot.log").read_text(encoding="utf-8")
    assert "goes to the new home only" not in old_log.read_text(encoding="utf-8")


def test_configuring_the_same_home_twice_does_not_duplicate_handlers(settings):
    configure_logging(settings)
    before = len(logging.getLogger("studybot").handlers)
    configure_logging(settings)
    assert len(logging.getLogger("studybot").handlers) == before
