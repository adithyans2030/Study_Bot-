import httpx
import pytest
from fastapi.testclient import TestClient

from app import __version__
from app.config import Settings
from app.main import create_app


@pytest.fixture
def settings(tmp_path):
    return Settings(home=tmp_path / "StudyBot", llm_model="llama3.2:3b", warm_on_start=False, _env_file=None)


@pytest.fixture
def client(settings):
    with TestClient(create_app(settings)) as test_client:
        yield test_client


def fake_models(models):
    async def _list_models(base_url, timeout=2.0):
        return models
    return _list_models


def test_health_is_liveness_only(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["version"] == __version__
    assert body["uptime_seconds"] >= 0


def test_startup_creates_data_dirs(client, settings):
    assert settings.uploads_dir.is_dir()
    assert settings.index_dir.is_dir()


def test_ready_when_everything_available(client, monkeypatch):
    monkeypatch.setattr("app.api.health.list_models", fake_models(["llama3.2:3b", "gemma2:2b"]))
    response = client.get("/api/ready")
    assert response.status_code == 200
    assert response.json()["ready"] is True


def test_not_ready_when_model_missing(client, monkeypatch):
    monkeypatch.setattr("app.api.health.list_models", fake_models(["gemma2:2b"]))
    response = client.get("/api/ready")
    assert response.status_code == 503
    body = response.json()
    assert body["checks"]["ollama"]["ok"] is True
    assert body["checks"]["llm_model"]["ok"] is False
    assert "ollama pull llama3.2:3b" in body["checks"]["llm_model"]["detail"]


def test_not_ready_when_ollama_down(client, monkeypatch):
    async def boom(base_url, timeout=2.0):
        raise httpx.ConnectError("connection refused")
    monkeypatch.setattr("app.api.health.list_models", boom)
    response = client.get("/api/ready")
    assert response.status_code == 503
    body = response.json()
    assert body["checks"]["ollama"]["ok"] is False
    assert body["checks"]["data_dir"]["ok"] is True


def test_bare_model_name_matches_latest_tag(tmp_path, monkeypatch):
    settings = Settings(home=tmp_path / "StudyBot", llm_model="gemma2", warm_on_start=False, _env_file=None)
    monkeypatch.setattr("app.api.health.list_models", fake_models(["gemma2:latest"]))
    with TestClient(create_app(settings)) as test_client:
        assert test_client.get("/api/ready").status_code == 200


def test_not_ready_when_the_embedding_model_could_not_load(client, monkeypatch):
    client.app.state.embedder_error = "Could not load model BAAI/bge-small-en-v1.5 from any source."
    monkeypatch.setattr("app.api.health.list_models", fake_models(["llama3.2:3b"]))
    response = client.get("/api/ready")
    assert response.status_code == 503
    check = response.json()["checks"]["embedding_model"]
    assert check["ok"] is False and "Could not load model" in check["detail"]
    client.app.state.embedder_error = None
    assert client.get("/api/ready").status_code == 200
