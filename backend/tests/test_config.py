import os
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.config import Settings, default_home


def test_default_home_uses_localappdata(monkeypatch, tmp_path):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    assert default_home() == tmp_path / "StudyBot"


def test_env_overrides(monkeypatch, tmp_path):
    monkeypatch.setenv("STUDYBOT_HOME", str(tmp_path / "sb"))
    monkeypatch.setenv("STUDYBOT_PORT", "9123")
    monkeypatch.setenv("STUDYBOT_LLM_MODEL", "qwen2.5:3b")
    settings = Settings(_env_file=None)
    assert settings.home == tmp_path / "sb"
    assert settings.port == 9123
    assert settings.llm_model == "qwen2.5:3b"


def test_rejects_home_inside_onedrive():
    with pytest.raises(ValidationError, match="OneDrive"):
        Settings(home=Path("C:/Users/someone/OneDrive/Desktop/StudyBot"), _env_file=None)


def test_rejects_onedrive_case_insensitive():
    with pytest.raises(ValidationError):
        Settings(home=Path("C:/Users/someone/onedrive - Personal/data"), _env_file=None)


def test_ensure_dirs_creates_layout(tmp_path):
    settings = Settings(home=tmp_path / "StudyBot", _env_file=None)
    settings.ensure_dirs()
    for directory in (settings.data_dir, settings.uploads_dir, settings.index_dir,
                      settings.logs_dir, settings.backups_dir):
        assert directory.is_dir()
    settings.ensure_dirs()  # idempotent


def test_a_folder_that_only_mentions_onedrive_in_its_name_is_allowed():
    """Regression: the guard blocked any path containing the word, e.g. a project-named temp folder."""
    settings = Settings(home=Path("C:/data/c--Users-adith-OneDrive-Desktop-Proj/StudyBot"), _env_file=None)
    assert settings.home.name == "StudyBot"
    Settings(home=Path("C:/data/not-onedrive-related/x"), _env_file=None)


def test_the_real_onedrive_location_from_the_environment_is_rejected(monkeypatch, tmp_path):
    monkeypatch.setenv("OneDrive", str(tmp_path / "Sync Root"))
    with pytest.raises(ValidationError, match="OneDrive"):
        Settings(home=tmp_path / "Sync Root" / "data", _env_file=None)
    Settings(home=tmp_path / "elsewhere", _env_file=None)


@pytest.mark.skipif(os.name != "nt", reason="the 260-character limit is a Windows rule")
def test_a_data_folder_too_long_for_windows_paths_is_rejected_with_advice():
    with pytest.raises(ValidationError, match="too long.*C:.StudyBot"):
        Settings(home=Path("C:/" + "deep/" * 30 + "StudyBot"), _env_file=None)
    Settings(home=Path("C:/StudyBot"), _env_file=None)
