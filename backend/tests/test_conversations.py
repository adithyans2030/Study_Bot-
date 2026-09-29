import sqlite3

import pytest

from app.core.conversations import Conversations, make_title
from app.rag.store import Store
from tests.test_migration import make_phase1_db


@pytest.fixture
def chats(tmp_path):
    return Conversations(Store(tmp_path / "t.db"))


def test_titles_are_single_short_lines():
    assert make_title("  What is\n  histogram   equalization? ") == "What is histogram equalization?"
    long = make_title("word " * 40)
    assert len(long) <= 60 and long.endswith("…")
    assert make_title("   ") == "New chat"


def test_conversations_hold_ordered_messages_with_sources_and_meta(chats):
    conv = chats.create(1, "What is Otsu thresholding?")
    assert conv.title == "What is Otsu thresholding?"
    chats.add_message(conv.id, 1, "user", "What is Otsu thresholding?")
    chats.add_message(conv.id, 1, "assistant", "It picks a threshold automatically [1].",
                      sources=[{"n": 1, "title": "Unit 2"}], meta={"cited": [1], "seconds": 4.2})
    first, second = chats.messages(conv.id, 1)
    assert (first.role, second.role) == ("user", "assistant")
    assert second.sources == [{"n": 1, "title": "Unit 2"}] and second.meta["cited"] == [1]
    assert chats.get(conv.id, 1).updated_at >= conv.updated_at


def test_conversations_are_private_to_their_owner(chats):
    conv = chats.create(1, "private question")
    chats.add_message(conv.id, 1, "user", "private question")
    assert chats.get(conv.id, 2) is None
    assert chats.messages(conv.id, 2) is None
    assert chats.list_for_user(2) == []
    assert chats.add_message(conv.id, 2, "user", "injected by someone else") is None
    assert chats.delete(conv.id, 2) is False
    assert [m.content for m in chats.messages(conv.id, 1)] == ["private question"], "nothing was written or deleted"


def test_list_is_newest_first_and_delete_removes_messages(chats):
    old = chats.create(1, "old chat")
    new = chats.create(1, "new chat")
    chats.add_message(old.id, 1, "user", "bump the old one")
    assert [c.id for c in chats.list_for_user(1)] == [old.id, new.id], "recently active conversations come first"
    chats.add_message(new.id, 1, "user", "x")
    assert chats.delete(new.id, 1) is True
    assert chats.delete(new.id, 1) is False
    with chats.store.connect() as con:
        assert con.execute("SELECT COUNT(*) FROM messages WHERE conversation_id = ?", (new.id,)).fetchone()[0] == 0


def test_recent_turns_pairs_questions_with_answers_and_skips_refusals(chats):
    conv = chats.create(1, "q1")
    script = [("user", "q1", {}), ("assistant", "a1", {}), ("user", "q2", {}),
              ("assistant", "I couldn't find that", {"refused": True}), ("user", "q3", {}),
              ("assistant", "a3", {}), ("user", "q4 unanswered", {})]
    for role, content, meta in script:
        chats.add_message(conv.id, 1, role, content, meta=meta)
    assert chats.recent_turns(conv.id, 1, limit=5) == [("q1", "a1"), ("q3", "a3")]
    assert chats.recent_turns(conv.id, 1, limit=1) == [("q3", "a3")]
    assert chats.recent_turns(conv.id, 2) == [], "another user gets no history"


def test_phase2_database_gains_conversation_tables_without_losing_data(tmp_path):
    path = tmp_path / "old.db"
    make_phase1_db(path)
    Store(path)  # phase 1 -> current
    store = Store(path)
    con = sqlite3.connect(path)
    assert con.execute("PRAGMA user_version").fetchone()[0] == 3
    assert {"conversations", "messages"} <= {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert len(store.list_documents()) == 2
    con.close()
