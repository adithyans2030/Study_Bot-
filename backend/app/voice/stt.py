"""Offline speech-to-text with faster-whisper (CTranslate2, CPU, int8). Nothing leaves the machine.

`base.en` transcribed a ~4 s question in 1.3-2 s on the development laptop but sometimes misspells
rare terms ("Laplation"); `small.en` is more accurate and 5-8x slower. Search is robust to the
misspellings (measured), and the recognised text is shown to the user, so `base.en` is the default.
"""
import logging
import threading
import time
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger("studybot.voice")
NO_SPEECH_SECONDS = 0.3  # less speech than this after silence removal counts as "nothing said"
_FILES = ["config.json", "model.bin", "tokenizer.json", "vocabulary.*", "preprocessor_config.json"]


class SpeechUnavailable(Exception):
    """Speech recognition cannot run (missing library, model not downloadable). Safe to show."""


class AudioTooLong(Exception):
    def __init__(self, seconds: float, limit: float):
        super().__init__(f"That recording is {seconds:.0f} s long; the limit is {limit:.0f} s.")


@dataclass(frozen=True)
class Transcript:
    text: str
    audio_seconds: float
    seconds: float  # time taken to transcribe


class Transcriber:
    def __init__(self, model_name: str, models_dir: Path, threads: int = 4):
        self.model_name = model_name
        self.models_dir = Path(models_dir)
        self.threads = threads
        self.language = "en" if model_name.endswith(".en") else None  # multilingual models detect it
        self._model = None
        self._load_lock = threading.Lock()
        self._run_lock = threading.Lock()  # one recording at a time: the model uses all CPU threads

    @property
    def loaded(self) -> bool:
        return self._model is not None

    @property
    def model_dir(self) -> Path:
        return self.models_dir / f"whisper-{self.model_name}"

    def _load(self):
        if self._model is not None:
            return self._model
        with self._load_lock:
            if self._model is None:
                try:
                    from faster_whisper import WhisperModel
                except ImportError as exc:
                    raise SpeechUnavailable("Speech recognition is not installed (pip install faster-whisper).") from exc
                try:
                    if not (self.model_dir / "model.bin").exists():
                        from huggingface_hub import snapshot_download
                        log.info("downloading speech model %s (first use only)", self.model_name)
                        # local_dir keeps plain files: the default cache uses symlinks, which fail on
                        # Windows without Developer Mode.
                        snapshot_download(f"Systran/faster-whisper-{self.model_name}", local_dir=str(self.model_dir),
                                          allow_patterns=_FILES)
                    self._model = WhisperModel(str(self.model_dir), device="cpu", compute_type="int8",
                                               cpu_threads=self.threads)
                except Exception as exc:
                    log.warning("speech model failed to load", exc_info=True)
                    raise SpeechUnavailable(f"The speech model could not be loaded: {str(exc)[:160]}") from exc
        return self._model

    def warm(self) -> None:
        self._load()

    def transcribe(self, path: Path, max_seconds: float = 120.0) -> Transcript:
        """Transcribe a recording. Raises AudioTooLong, SpeechUnavailable, or ValueError for undecodable audio."""
        model = self._load()
        started = time.perf_counter()
        with self._run_lock:
            try:
                segments, info = model.transcribe(str(path), language=self.language, vad_filter=True, beam_size=1,
                                                  condition_on_previous_text=False)
            except Exception as exc:
                raise ValueError("Could not read that recording.") from exc
            if info.duration > max_seconds:
                raise AudioTooLong(info.duration, max_seconds)
            try:
                text = " ".join(s.text.strip() for s in segments).strip()
            except Exception as exc:
                raise ValueError("Could not read that recording.") from exc
            if getattr(info, "duration_after_vad", info.duration) < NO_SPEECH_SECONDS:
                text = ""  # silence: Whisper tends to invent phrases like "Thank you." here
        return Transcript(text, float(info.duration), time.perf_counter() - started)
