import pytest

from app import cli
from app.rag.pipeline import StudyBot
from tests.fixtures import notes_docx


@pytest.fixture
def run(monkeypatch, settings, embedder, capsys):
    monkeypatch.setattr(cli, "Settings", lambda: settings)
    monkeypatch.setattr(cli, "StudyBot", lambda s: StudyBot(s, embedder=embedder))

    def invoke(*argv):
        code = cli.main(list(argv))
        captured = capsys.readouterr()
        return code, captured.out, captured.err
    return invoke


def test_ingest_list_search_delete_roundtrip(run, tmp_path):
    path = notes_docx(tmp_path / "Unit_Notes.docx")

    code, out, _ = run("ingest", str(path), "-c", "cv")
    assert code == 0 and "indexed: Unit Notes [docx]" in out

    code, out, _ = run("ingest", str(path), "-c", "cv")
    assert code == 0 and "already up to date (skipped)" in out

    code, out, _ = run("list")
    assert code == 0 and "cv: 1 document(s)" in out and "#1 [docx] Unit Notes" in out

    code, out, _ = run("search", "how many pixels does bicubic use", "-c", "cv")
    assert code == 0 and "Unit Notes" in out and "cosine=" in out

    code, out, _ = run("delete", "1")
    assert code == 0 and "deleted" in out
    code, out, _ = run("delete", "1")
    assert code == 1 and "no document with id 1" in out


def test_ask_warns_about_nonexistent_citations_and_lists_real_sources(run, settings, tmp_path, monkeypatch):
    from app.core.ollama import ChatChunk
    from app.rag import pipeline as pipeline_module

    settings.min_dense_score = 0.0  # the hashing test embedder's cosines are far below a real model's

    async def stream(base_url, model, messages, **kwargs):
        yield ChatChunk("Bicubic uses 16 pixels [1] and more [7].")
        yield ChatChunk("", True, eval_count=5, eval_seconds=1.0)

    monkeypatch.setattr(pipeline_module, "chat_stream", stream)
    run("ingest", str(notes_docx(tmp_path / "Unit_Notes.docx")), "-c", "cv")
    code, out, _ = run("ask", "how many pixels does bicubic use", "-c", "cv")
    assert code == 0
    assert "note: the model cited 1 source number(s) that do not exist" in out
    assert "Sources:" in out and "[1] Unit Notes" in out


def test_list_when_empty_explains_what_to_do(run):
    code, out, _ = run("list")
    assert code == 0 and "Nothing indexed yet" in out


def test_ingest_error_is_reported_not_raised(run, tmp_path):
    code, _, err = run("ingest", str(tmp_path / "missing.pdf"))
    assert code == 1 and "error: File not found" in err


def test_unknown_collection_is_reported(run):
    code, _, err = run("search", "anything", "-c", "nope")
    assert code == 1 and "no collection named" in err


def test_cli_works_on_the_owners_library_once_accounts_exist(run, tmp_path, settings, embedder):
    from app.core.accounts import Accounts
    from app.rag.store import Store

    path = notes_docx(tmp_path / "Unit_Notes.docx")
    assert run("ingest", str(path), "-c", "cv")[0] == 0  # before any account: local owner

    accounts = Accounts(Store(settings.db_path))
    owner = accounts.create_user("alice", "correct horse")  # adopts the collection
    accounts.create_user("bob", "another passphrase")

    code, out, _ = run("list")
    assert code == 0 and "cv: 1 document(s)" in out, "default user is now the owner"
    code, out, _ = run("--user", "bob", "list")
    assert "Nothing indexed yet" in out, "another user's library is separate"
    code, _, err = run("--user", "nobody", "list")
    assert code == 1 and "No user named 'nobody'" in err
    assert Store(settings.db_path).list_collections(owner.id)[0]["name"] == "cv"
