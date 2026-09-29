"""Application settings, read from STUDYBOT_* environment variables or a .env file."""
import os
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def default_home() -> Path:
    """Runtime data root. Kept outside OneDrive so sync never touches live databases."""
    local = os.environ.get("LOCALAPPDATA")
    if local:
        return Path(local) / "StudyBot"
    return Path.home() / ".studybot"


MAX_HOME_LENGTH = 110


def _inside_onedrive(path: Path) -> bool:
    """True if `path` is inside a OneDrive-synced folder. OneDrive roots are named 'OneDrive' or
    'OneDrive - <organisation>', and Windows also records the real location in environment
    variables. A folder that merely has 'onedrive' somewhere in its name is not synced."""
    resolved = path.resolve()
    if any(part.lower().startswith("onedrive") for part in resolved.parts):
        return True
    for variable in ("OneDrive", "OneDriveConsumer", "OneDriveCommercial"):
        root = os.environ.get(variable)
        if root and resolved.is_relative_to(Path(root).resolve()):
            return True
    return False


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="STUDYBOT_", env_file=".env", extra="ignore")

    home: Path = Field(default_factory=default_home)
    host: str = "127.0.0.1"
    port: int = 8000
    ollama_url: str = "http://127.0.0.1:11434"
    llm_model: str = "gemma2:2b"
    num_ctx: int = 4096  # Ollama's default is 2048, which silently truncates RAG prompts

    # Web / accounts
    max_upload_mb: int = 100
    session_days: int = 14
    allow_registration: bool = False  # the first account can always register; later ones need this on
    cookie_secure: bool = False  # set true when served over HTTPS (e.g. through Tailscale)
    allowed_origins: str = ""  # extra origins allowed to make state-changing requests, comma separated
    login_max_failures: int = 5  # failed logins per username+IP per 5 minutes
    warm_on_start: bool = True  # load the embedding model and the LLM in the background at startup

    # How follow-up questions are searched: off | concat | llm (see app/rag/followup.py). "llm" found
    # 100% of follow-ups AND left independent questions alone; it costs ~2 s, only on follow-ups.
    followup_mode: str = "llm"
    history_turns: int = 3  # earlier exchanges used to understand a follow-up

    # Voice input, fully offline. base.en took ~1.5 s per spoken question; small.en is more accurate
    # on rare technical terms but 5-8x slower on this CPU. Speaking is done by the browser.
    voice_enabled: bool = True
    stt_model: str = "base.en"
    stt_threads: int = 4
    max_audio_mb: int = 10
    max_audio_seconds: int = 120

    embed_model: str = "BAAI/bge-small-en-v1.5"
    rerank_model: str = "Xenova/ms-marco-MiniLM-L-6-v2"
    use_reranker: bool = False
    # Chunks sent to the LLM. On this GPU, prompt processing dominates latency (~130 tok/s):
    # 4 chunks gave ~6 s to first token vs ~11 s with 6, with no accuracy loss on a 12-question test.
    retrieve_k: int = 4
    candidates: int = 30
    # Below this best-match cosine (bge-small), skip the LLM and say "not in your materials".
    # 0.55 is provisional: it falsely refused 0 of 67 answerable questions on the golden set. Re-run
    # `python -m eval.run_retrieval` to recalibrate as the golden set grows.
    min_dense_score: float = 0.55

    # Sizes are approximate tokens; bge-small truncates input at 512.
    chunk_target_tokens: int = 320
    chunk_max_tokens: int = 420
    chunk_min_tokens: int = 80
    chunk_overlap_tokens: int = 40

    @field_validator("home")
    @classmethod
    def home_must_not_be_synced(cls, value: Path) -> Path:
        if _inside_onedrive(value):
            raise ValueError(
                f"STUDYBOT_HOME={value} is inside OneDrive. Syncing live SQLite/vector "
                "files corrupts them; choose a path outside OneDrive."
            )
        return value

    @field_validator("home")
    @classmethod
    def home_must_fit_windows_paths(cls, value: Path) -> Path:
        # Model files live several folders deep (~130 characters below `home`) and Windows rejects
        # paths over 260 characters, with an unhelpful "filename too long" error at first use.
        if os.name == "nt" and len(str(value.resolve())) > MAX_HOME_LENGTH:
            raise ValueError(
                f"STUDYBOT_HOME is too long ({len(str(value.resolve()))} characters). Windows limits file paths "
                f"to 260 characters and the model files need about 130 of them. Use a shorter folder, "
                f"e.g. C:\\StudyBot."
            )
        return value

    @property
    def data_dir(self) -> Path:
        return self.home / "data"

    @property
    def uploads_dir(self) -> Path:
        return self.home / "uploads"

    @property
    def index_dir(self) -> Path:
        return self.home / "index"

    @property
    def logs_dir(self) -> Path:
        return self.home / "logs"

    @property
    def backups_dir(self) -> Path:
        return self.home / "backups"

    @property
    def models_dir(self) -> Path:
        """Embedding/reranker model files. Never the OS temp dir, which Windows may clean."""
        return self.home / "models"

    @property
    def cache_dir(self) -> Path:
        return self.home / "cache"

    @property
    def db_path(self) -> Path:
        return self.data_dir / "studybot.db"

    def ensure_dirs(self) -> None:
        for directory in (self.data_dir, self.uploads_dir, self.index_dir, self.logs_dir,
                          self.backups_dir, self.models_dir, self.cache_dir):
            directory.mkdir(parents=True, exist_ok=True)
