"""Saved chats. A conversation belongs to one user; every read and write is scoped to that user, so
one account can never see or change another's history."""
import json
import re
import time
from dataclasses import dataclass, field

from app.rag.store import Store

TITLE_LENGTH = 60


@dataclass(frozen=True)
class Conversation:
    id: int
    title: str
    created_at: float
    updated_at: float

    def public(self) -> dict:
        return {"id": self.id, "title": self.title, "updated_at": self.updated_at}


@dataclass(frozen=True)
class Message:
    id: int
    role: str  # user | assistant
    content: str
    sources: list = field(default_factory=list)
    meta: dict = field(default_factory=dict)
    created_at: float = 0.0

    def public(self) -> dict:
        return {"id": self.id, "role": self.role, "content": self.content, "sources": self.sources,
                "meta": self.meta, "created_at": self.created_at}


def make_title(question: str) -> str:
    line = re.sub(r"\s+", " ", question).strip()
    return (line[: TITLE_LENGTH - 1].rstrip() + "…") if len(line) > TITLE_LENGTH else (line or "New chat")


class Conversations:
    def __init__(self, store: Store):
        self.store = store

    def create(self, user_id: int, first_question: str) -> Conversation:
        now = time.time()
        with self.store.transaction() as con:
            conversation_id = con.execute(
                "INSERT INTO conversations (user_id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
                (user_id, make_title(first_question), now, now)).lastrowid
        return self.get(conversation_id, user_id)

    def get(self, conversation_id: int, user_id: int) -> Conversation | None:
        with self.store.connect() as con:
            row = con.execute("SELECT * FROM conversations WHERE id = ? AND user_id = ?",
                              (conversation_id, user_id)).fetchone()
        return Conversation(row["id"], row["title"], row["created_at"], row["updated_at"]) if row else None

    def list_for_user(self, user_id: int, limit: int = 50) -> list[Conversation]:
        with self.store.connect() as con:
            rows = con.execute("SELECT * FROM conversations WHERE user_id = ? ORDER BY updated_at DESC, id DESC LIMIT ?",
                               (user_id, limit)).fetchall()
        return [Conversation(r["id"], r["title"], r["created_at"], r["updated_at"]) for r in rows]

    def delete(self, conversation_id: int, user_id: int) -> bool:
        with self.store.transaction() as con:
            return con.execute("DELETE FROM conversations WHERE id = ? AND user_id = ?",
                               (conversation_id, user_id)).rowcount > 0

    def add_message(self, conversation_id: int, user_id: int, role: str, content: str,
                    sources: list | None = None, meta: dict | None = None) -> Message | None:
        """Append a message. Returns None (and writes nothing) if the conversation is not this user's."""
        now = time.time()
        with self.store.transaction() as con:
            owned = con.execute("SELECT 1 FROM conversations WHERE id = ? AND user_id = ?",
                                (conversation_id, user_id)).fetchone()
            if not owned:
                return None
            message_id = con.execute(
                "INSERT INTO messages (conversation_id, role, content, sources, meta, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (conversation_id, role, content, json.dumps(sources or []), json.dumps(meta or {}), now)).lastrowid
            con.execute("UPDATE conversations SET updated_at = ? WHERE id = ?", (now, conversation_id))
        return Message(message_id, role, content, sources or [], meta or {}, now)

    def messages(self, conversation_id: int, user_id: int) -> list[Message] | None:
        """All messages in order, or None if the conversation is not this user's."""
        if self.get(conversation_id, user_id) is None:
            return None
        with self.store.connect() as con:
            rows = con.execute("SELECT * FROM messages WHERE conversation_id = ? ORDER BY id",
                               (conversation_id,)).fetchall()
        return [Message(r["id"], r["role"], r["content"], json.loads(r["sources"]), json.loads(r["meta"]),
                        r["created_at"]) for r in rows]

    def recent_turns(self, conversation_id: int, user_id: int, limit: int = 3) -> list[tuple[str, str]]:
        """The last `limit` completed (question, answer) exchanges, oldest first. Refusals and empty
        answers are skipped: they say nothing about what a follow-up refers to."""
        messages = self.messages(conversation_id, user_id) or []
        turns, pending = [], None
        for message in messages:
            if message.role == "user":
                pending = message.content
            elif pending is not None:
                if not message.meta.get("refused") and not message.meta.get("empty"):
                    turns.append((pending, message.content))
                pending = None
        return turns[-limit:]
