import hashlib
import re

import numpy as np
import pytest

from app.config import Settings


class HashEmbedder:
    """Deterministic bag-of-words embedder, so tests need no model download."""
    DIM = 256

    def _vec(self, text: str) -> np.ndarray:
        vec = np.zeros(self.DIM, dtype=np.float32)
        for word in re.findall(r"[a-z0-9]+", text.lower()):
            vec[int(hashlib.md5(word.encode()).hexdigest(), 16) % self.DIM] += 1.0
        norm = np.linalg.norm(vec)
        return vec / norm if norm else vec

    def embed_passages(self, texts):
        return np.vstack([self._vec(t) for t in texts])

    def embed_query(self, query):
        return self._vec(query)


@pytest.fixture
def embedder():
    return HashEmbedder()


@pytest.fixture
def settings(tmp_path):
    return Settings(home=tmp_path / "StudyBot", warm_on_start=False, _env_file=None)
