"""Speech input: recording validation, the transcriber's behaviour, and the endpoint."""
import asyncio
import io
import sys
import types
import wave
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.uploads import UploadError
from app.main import create_app
from app.rag.pipeline import StudyBot
from app.voice import audio
from app.voice.stt import AudioTooLong, SpeechUnavailable, Transcriber, Transcript
from tests.test_api import sign_up


def wav_bytes(seconds=0.3, rate=16000) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(rate)
        out.writeframes(b"\x00\x00" * int(rate * seconds))
    return buffer.getvalue()


WEBM = b"\x1a\x45\xdf\xa3" + b"\x00" * 200
MP4 = b"\x00\x00\x00\x18ftypM4A " + b"\x00" * 200


# ---- container check ---------------------------------------------------------------------

@pytest.mark.parametrize("head,kind", [
    (WEBM[:16], "webm"), (b"OggS" + b"\0" * 12, "ogg"), (wav_bytes()[:16], "wav"), (MP4[:16], "mp4"),
    (b"ID3\x03" + b"\0" * 12, "mp3"), (b"\xff\xfb\x90\x00" + b"\0" * 12, "mp3"), (b"fLaC" + b"\0" * 12, "flac"),
])
def test_only_browser_recordable_containers_are_accepted(head, kind):
    assert audio.sniff_audio(head) == kind


@pytest.mark.parametrize("head", [b"", b"MZ\x90\x00" + b"\0" * 12, b"%PDF-1.7\n" + b"\0" * 8, b"<html>" + b"\0" * 10,
                                  b"PK\x03\x04" + b"\0" * 12, b"\x7fELF" + b"\0" * 12])
def test_other_files_are_never_handed_to_the_decoder(head):
    assert audio.sniff_audio(head) is None


class FakeUpload:
    def __init__(self, data):
        self.data, self.pos = data, 0

    async def read(self, size=-1):
        chunk = self.data[self.pos:] if size < 0 else self.data[self.pos:self.pos + size]
        self.pos += len(chunk)
        return chunk


def save(tmp_path, data, limit=1_000_000):
    return asyncio.run(audio.save_recording(FakeUpload(data), tmp_path / "voice", limit))


def test_a_valid_recording_is_stored_with_the_detected_extension_and_can_be_discarded(tmp_path):
    path = save(tmp_path, WEBM)
    assert path.suffix == ".webm" and path.read_bytes() == WEBM
    audio.discard(path)
    assert not path.exists()
    audio.discard(path)  # already gone: no error


@pytest.mark.parametrize("data,limit,status", [(b"", 1000, 400), (b"not audio at all " * 4, 1000, 415), (WEBM, 100, 413)])
def test_bad_recordings_are_rejected_and_leave_nothing_behind(tmp_path, data, limit, status):
    with pytest.raises(UploadError) as err:
        save(tmp_path, data, limit)
    assert err.value.status == status
    assert list((tmp_path / "voice").iterdir()) == []


# ---- the transcriber (with a stand-in for the heavy model) -------------------------------

class Seg:
    def __init__(self, text):
        self.text = text


class FakeWhisper:
    instances = []

    def __init__(self, path, device, compute_type, cpu_threads):
        self.args = (path, device, compute_type, cpu_threads)
        self.calls = []
        self.reply = ([Seg(" What is Sobel? "), Seg("and Laplacian")], types.SimpleNamespace(duration=4.0, duration_after_vad=3.5))
        self.error = None
        FakeWhisper.instances.append(self)

    def transcribe(self, path, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return self.reply


@pytest.fixture
def fake_libs(monkeypatch):
    FakeWhisper.instances = []
    downloads = []
    monkeypatch.setitem(sys.modules, "faster_whisper", types.SimpleNamespace(WhisperModel=FakeWhisper))

    def snapshot_download(repo_id, local_dir, allow_patterns):
        downloads.append((repo_id, local_dir, allow_patterns))
        Path(local_dir).mkdir(parents=True, exist_ok=True)
        (Path(local_dir) / "model.bin").write_bytes(b"x")

    monkeypatch.setitem(sys.modules, "huggingface_hub", types.SimpleNamespace(snapshot_download=snapshot_download))
    return downloads


def test_model_is_downloaded_once_without_symlinks_and_loaded_on_cpu_int8(tmp_path, fake_libs):
    transcriber = Transcriber("base.en", tmp_path, threads=3)
    assert not transcriber.loaded
    transcriber.warm()
    assert transcriber.loaded
    assert fake_libs == [("Systran/faster-whisper-base.en", str(tmp_path / "whisper-base.en"),
                          ["config.json", "model.bin", "tokenizer.json", "vocabulary.*", "preprocessor_config.json"])]
    assert FakeWhisper.instances[0].args == (str(tmp_path / "whisper-base.en"), "cpu", "int8", 3)
    Transcriber("base.en", tmp_path).warm()
    assert len(fake_libs) == 1, "an already-downloaded model is not downloaded again"


def test_transcript_text_is_joined_and_options_are_sensible(tmp_path, fake_libs):
    transcriber = Transcriber("base.en", tmp_path)
    result = transcriber.transcribe(tmp_path / "x.wav")
    assert result == Transcript("What is Sobel? and Laplacian", 4.0, result.seconds)
    options = FakeWhisper.instances[0].calls[0]
    assert options["language"] == "en" and options["vad_filter"] is True and options["beam_size"] == 1
    assert Transcriber("small", tmp_path).language is None, "multilingual models detect the language"


def test_silence_yields_no_text_instead_of_a_hallucination(tmp_path, fake_libs):
    transcriber = Transcriber("base.en", tmp_path)
    transcriber.warm()
    FakeWhisper.instances[0].reply = ([Seg("Thank you.")], types.SimpleNamespace(duration=2.0, duration_after_vad=0.1))
    assert transcriber.transcribe(tmp_path / "x.wav").text == ""


def test_long_recordings_are_refused_before_transcribing(tmp_path, fake_libs):
    transcriber = Transcriber("base.en", tmp_path)
    with pytest.raises(AudioTooLong, match="limit is 3 s"):
        transcriber.transcribe(tmp_path / "x.wav", max_seconds=3)


def test_undecodable_audio_is_a_value_error(tmp_path, fake_libs):
    transcriber = Transcriber("base.en", tmp_path)
    transcriber.warm()
    FakeWhisper.instances[0].error = RuntimeError("invalid data found when processing input /secret/path")
    with pytest.raises(ValueError) as err:
        transcriber.transcribe(tmp_path / "x.wav")
    assert "secret" not in str(err.value), "decoder messages (which can contain paths) are not passed on"


def test_missing_library_or_model_becomes_speech_unavailable(tmp_path, monkeypatch):
    monkeypatch.setitem(sys.modules, "faster_whisper", None)  # import fails
    with pytest.raises(SpeechUnavailable, match="not installed"):
        Transcriber("base.en", tmp_path).warm()

    monkeypatch.setitem(sys.modules, "faster_whisper", types.SimpleNamespace(WhisperModel=FakeWhisper))

    def failing_download(**kwargs):
        raise OSError("network down")

    monkeypatch.setitem(sys.modules, "huggingface_hub", types.SimpleNamespace(snapshot_download=failing_download))
    with pytest.raises(SpeechUnavailable, match="could not be loaded"):
        Transcriber("base.en", tmp_path).warm()


# ---- the endpoint ------------------------------------------------------------------------

class StubTranscriber:
    model_name = "base.en"
    loaded = True

    def __init__(self):
        self.reply, self.error, self.seen = Transcript("what is the sobel operator", 3.0, 1.2), None, []

    def transcribe(self, path, max_seconds=120):
        self.seen.append((Path(path).suffix, Path(path).exists(), max_seconds))
        if self.error:
            raise self.error
        return self.reply


@pytest.fixture
def stub():
    return StubTranscriber()


@pytest.fixture
def voice_app(settings, embedder, stub):
    settings.followup_mode = "concat"
    return create_app(settings, StudyBot(settings, embedder=embedder), transcriber=stub)


@pytest.fixture
def web(voice_app):
    with TestClient(voice_app) as client:
        sign_up(client)
        yield client


def send(web, data, name="rec.webm"):
    return web.post("/api/voice/transcribe", files={"audio": (name, data, "audio/webm")})


def test_a_recording_is_transcribed_and_the_temp_file_is_removed(web, voice_app, stub):
    response = send(web, WEBM)
    assert response.status_code == 200
    assert response.json() == {"text": "what is the sobel operator", "audio_seconds": 3.0, "seconds": 1.2}
    assert stub.seen == [(".webm", True, 120)], "the decoder saw a real file with the detected extension"
    folder = voice_app.state.settings.cache_dir / "voice"
    assert not folder.exists() or list(folder.iterdir()) == [], "the audio is never kept"


def test_the_container_is_decided_by_contents_not_by_filename(web, stub):
    assert send(web, wav_bytes(), name="looks-like.webm").status_code == 200
    assert stub.seen[-1][0] == ".wav"
    assert send(web, b"MZ" + b"\0" * 200, name="song.mp3").status_code == 415
    assert send(web, b"", name="empty.webm").status_code == 400
    assert len(stub.seen) == 1, "rejected files never reach the transcriber"


def test_limits_and_failures_give_clear_errors(web, voice_app, stub):
    voice_app.state.settings.max_audio_mb = 1
    assert send(web, WEBM + b"0" * (2 * 1024 * 1024)).status_code == 413
    voice_app.state.settings.max_audio_mb = 10

    stub.error = AudioTooLong(300, 120)
    assert send(web, WEBM).status_code == 413
    stub.error = ValueError("Could not read that recording.")
    bad = send(web, WEBM)
    assert bad.status_code == 400 and "Could not read" in bad.json()["detail"]
    stub.error = SpeechUnavailable("The speech model could not be loaded: offline")
    down = send(web, WEBM)
    assert down.status_code == 503 and "offline" in down.json()["detail"]
    folder = voice_app.state.settings.cache_dir / "voice"
    assert not folder.exists() or list(folder.iterdir()) == []


def test_status_reports_availability_and_a_recorded_failure(web, voice_app, stub):
    assert web.get("/api/voice/status").json() == {"available": True, "ready": True, "model": "base.en", "error": None}
    stub.error = SpeechUnavailable("model missing")
    send(web, WEBM)
    status = web.get("/api/voice/status").json()
    assert status["available"] is False and status["error"] == "model missing"


def test_voice_requires_sign_in(voice_app):
    with TestClient(voice_app) as anonymous:
        assert anonymous.get("/api/voice/status").status_code == 401
        assert send(anonymous, WEBM).status_code == 401


def test_voice_can_be_switched_off(settings, embedder):
    settings.voice_enabled = False
    with TestClient(create_app(settings, StudyBot(settings, embedder=embedder))) as client:
        sign_up(client)
        assert client.get("/api/voice/status").json()["model"] is None
        assert send(client, WEBM).status_code == 503
