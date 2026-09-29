"""Local accounts and login sessions.

Passwords are hashed with argon2id. Session tokens are random 256-bit values; only their SHA-256
is stored, so a leaked database does not leak usable sessions. The token travels in an HttpOnly
cookie (see app/api/auth.py).
"""
import hashlib
import re
import secrets
import sqlite3
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from app.rag.store import Store

_USERNAME = re.compile(r"^[a-z0-9][a-z0-9_.-]{2,31}$")
MIN_PASSWORD, MAX_PASSWORD = 8, 128
_hasher = PasswordHasher()
_DUMMY_HASH = _hasher.hash("not-a-real-password")  # verified against when the user does not exist


class AccountError(Exception):
    """A registration/login problem whose message is safe to show to the user."""


@dataclass(frozen=True)
class User:
    id: int
    username: str
    is_admin: bool


def validate_username(username: str) -> str:
    username = (username or "").strip().lower()
    if not _USERNAME.match(username):
        raise AccountError("Username must be 3-32 characters: letters, numbers, dot, dash or underscore.")
    return username


def validate_password(password: str) -> str:
    if not isinstance(password, str) or len(password) < MIN_PASSWORD:
        raise AccountError(f"Password must be at least {MIN_PASSWORD} characters.")
    if len(password) > MAX_PASSWORD:
        raise AccountError(f"Password must be at most {MAX_PASSWORD} characters.")
    return password


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class Accounts:
    def __init__(self, store: Store, session_days: int = 14):
        self.store = store
        self.session_seconds = session_days * 86400

    def user_count(self) -> int:
        with self.store.connect() as con:
            return con.execute("SELECT COUNT(*) FROM users").fetchone()[0]

    def owner_id(self) -> int | None:
        """The first admin account (the person who set the system up), if any."""
        with self.store.connect() as con:
            row = con.execute("SELECT id FROM users WHERE is_admin = 1 ORDER BY id LIMIT 1").fetchone()
            return row["id"] if row else None

    def get_by_username(self, username: str) -> User | None:
        with self.store.connect() as con:
            row = con.execute("SELECT id, username, is_admin FROM users WHERE username = ?",
                              (username.strip().lower(),)).fetchone()
            return User(row["id"], row["username"], bool(row["is_admin"])) if row else None

    def create_user(self, username: str, password: str) -> User:
        """Create an account. The very first account becomes the admin and adopts any collections
        created from the command line before accounts existed."""
        username, password = validate_username(username), validate_password(password)
        password_hash = _hasher.hash(password)
        try:
            with self.store.transaction() as con:
                is_admin = con.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0
                user_id = con.execute("INSERT INTO users (username, password_hash, is_admin) VALUES (?, ?, ?)",
                                      (username, password_hash, int(is_admin))).lastrowid
        except sqlite3.IntegrityError as exc:
            raise AccountError("That username is already taken.") from exc
        if is_admin:
            self.store.adopt_legacy_collections(user_id)
        return User(user_id, username, is_admin)

    def authenticate(self, username: str, password: str) -> User | None:
        with self.store.connect() as con:
            row = con.execute("SELECT id, username, is_admin, password_hash FROM users WHERE username = ?",
                              ((username or "").strip().lower(),)).fetchone()
        stored = row["password_hash"] if row else _DUMMY_HASH  # same work whether or not the user exists
        try:
            _hasher.verify(stored, password or "")
        except (VerificationError, InvalidHashError):
            return None
        if not row:
            return None
        if _hasher.check_needs_rehash(stored):
            with self.store.transaction() as con:
                con.execute("UPDATE users SET password_hash = ? WHERE id = ?", (_hasher.hash(password), row["id"]))
        return User(row["id"], row["username"], bool(row["is_admin"]))

    # ---- sessions ----------------------------------------------------------------------

    def create_session(self, user_id: int) -> str:
        token = secrets.token_urlsafe(32)
        with self.store.transaction() as con:
            con.execute("DELETE FROM sessions WHERE expires_at < ?", (time.time(),))
            con.execute("INSERT INTO sessions (token_hash, user_id, expires_at) VALUES (?, ?, ?)",
                        (_token_hash(token), user_id, time.time() + self.session_seconds))
        return token

    def user_for_token(self, token: str | None) -> User | None:
        if not token:
            return None
        with self.store.connect() as con:
            row = con.execute(
                "SELECT u.id, u.username, u.is_admin FROM sessions s JOIN users u ON u.id = s.user_id "
                "WHERE s.token_hash = ? AND s.expires_at > ?", (_token_hash(token), time.time())).fetchone()
        return User(row["id"], row["username"], bool(row["is_admin"])) if row else None

    def end_session(self, token: str | None) -> None:
        if token:
            with self.store.transaction() as con:
                con.execute("DELETE FROM sessions WHERE token_hash = ?", (_token_hash(token),))


class LoginLimiter:
    """Slow down password guessing: at most `limit` failed attempts per key in `window` seconds."""

    def __init__(self, limit: int = 5, window: float = 300.0, clock=time.monotonic):
        self.limit, self.window, self.clock = limit, window, clock
        self._failures: dict[str, deque] = defaultdict(deque)
        self._lock = threading.Lock()

    def _prune(self, key: str) -> deque:
        q = self._failures[key]
        while q and self.clock() - q[0] > self.window:
            q.popleft()
        return q

    def retry_after(self, key: str) -> int:
        """Seconds until another attempt is allowed (0 if allowed now)."""
        with self._lock:
            q = self._prune(key)
            if len(q) < self.limit:
                return 0
            return max(1, int(self.window - (self.clock() - q[0])))

    def record_failure(self, key: str) -> None:
        with self._lock:
            self._prune(key).append(self.clock())

    def reset(self, key: str) -> None:
        with self._lock:
            self._failures.pop(key, None)
