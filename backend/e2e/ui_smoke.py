"""Real-browser smoke test of the dashboard against a RUNNING server.

It registers the first account, uploads a PDF, asks real questions (this needs Ollama running),
asks a follow-up, checks saved chats, optionally asks BY VOICE (a WAV file is played into the
browser as a fake microphone, so the real recorder, server and speech model are exercised), checks
read-aloud, the installable-app files and the "computer is off" screen, then signs out and in,
deletes the document, and checks the phone layout. It watches the browser console, so a
Content-Security-Policy violation or a script error fails the run.

Not part of `pytest` (it needs a browser, a live server and Ollama). Use a FRESH data folder,
because the first step creates the owner account:

    $env:STUDYBOT_HOME = "C:\\StudyBot-smoke"; $env:STUDYBOT_PORT = "8766"
    python -m uvicorn app.main:create_app --factory --port 8766         # in one terminal
    python e2e/ui_smoke.py --pdf C:\\path\\to\\notes.pdf --follow-up "Which one is noisier?" `
        --voice-wav C:\\path\\to\\question.wav                         # in another

Needs Playwright with Chromium:  pip install playwright ; python -m playwright install chromium
"""
import argparse
import json
import pathlib
import re
import sys
import tempfile
import time
import urllib.request

from playwright.sync_api import expect, sync_playwright

PASSWORD = "correct horse battery"
results: list[tuple[str, bool]] = []
console_problems: list[tuple[str, str]] = []
spoken: list[str] = []

# Replace speech output with a recorder: deterministic, silent, and works in headless browsers.
SPEAK_HOOK = """
(() => {
  if (!window.speechSynthesis) return;
  window.speechSynthesis.speak = (utterance) => { window.record_spoken(utterance.text); };
})();
"""


def check(name: str, condition: bool, detail: str = "") -> None:
    results.append((name, bool(condition)))
    print(("PASS " if condition else "FAIL ") + name + (f"  [{detail}]" if detail else ""), flush=True)


def wait_for_server(base: str, timeout: int = 120) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(base + "/api/health", timeout=3):
                return
        except Exception:
            time.sleep(1)
    sys.exit(f"Server at {base} did not become healthy.")


def watch(page) -> None:
    page.on("console", lambda m: console_problems.append((m.type, m.text)) if m.type in ("error", "warning") else None)
    page.on("pageerror", lambda e: console_problems.append(("pageerror", str(e))))


def finish_of(page, before_bots: int, timeout: int) -> dict:
    """Wait for a new assistant message to finish streaming, then describe it."""
    expect(page.locator(".msg.bot")).to_have_count(before_bots + 1, timeout=timeout)
    expect(page.locator("#send")).to_have_text("Ask", timeout=timeout)  # the stream has finished
    last = page.locator(".msg.bot").last
    return {
        "answer": last.locator(".answer").inner_text() if last.locator(".answer:not([hidden])").count() else "",
        "flags": [t.strip() for t in last.locator(".flag").all_inner_texts()],
        "sources": [t.strip() for t in last.locator(".source").all_inner_texts()],
        "searched": last.locator(".searched").inner_text() if last.locator(".searched:not([hidden])").count() else "",
        "refused": "refused" in (last.locator(".answer").get_attribute("class") or ""),
    }


def ask(page, question: str, timeout: int = 180_000) -> dict:
    before = page.locator(".msg.bot").count()
    page.fill("#question", question)
    page.press("#question", "Enter")
    return finish_of(page, before, timeout)


def new_page(browser, **options):
    context = browser.new_context(**options)
    page = context.new_page()
    watch(page)
    return context, page


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--url", default="http://127.0.0.1:8766")
    parser.add_argument("--pdf", required=True, type=pathlib.Path, help="a text-based PDF with an answerable topic")
    parser.add_argument("--question", default="What is the main topic of this document?", help="a question the PDF can answer")
    parser.add_argument("--follow-up", default=None, help="a follow-up to --question that needs its context (optional)")
    parser.add_argument("--voice-wav", type=pathlib.Path, default=None,
                        help="a WAV of someone asking a question the PDF can answer, played as a fake microphone (optional)")
    parser.add_argument("--out", type=pathlib.Path, default=pathlib.Path(tempfile.gettempdir()) / "studybot-smoke")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    args.out.mkdir(parents=True, exist_ok=True)
    wait_for_server(args.url)

    launch_args = []
    if args.voice_wav:  # play the WAV once as the microphone, then silence
        launch_args = ["--use-fake-device-for-media-stream", "--use-fake-ui-for-media-stream",
                       f"--use-file-for-fake-audio-capture={args.voice_wav.resolve()}%noloop"]

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=launch_args)

        # ---- desktop, light theme. The Content-Security-Policy stays enforced here.
        context, page = new_page(browser, viewport={"width": 1280, "height": 820}, color_scheme="light",
                                 permissions=["microphone"])
        page.expose_function("record_spoken", lambda text: spoken.append(text))
        page.add_init_script(SPEAK_HOOK)
        page.goto(args.url)
        page.wait_for_selector(".auth-card")
        check("first visit offers to create the owner account", "first account" in page.inner_text(".lede"))
        page.fill("#username", "alice")
        page.fill("#password", "short")
        page.click("button[type=submit]")
        page.wait_for_selector(".error-text:not(:empty)")
        check("weak password shows a clear error", "at least 8" in page.inner_text(".error-text"))
        page.fill("#password", PASSWORD)
        page.click("button[type=submit]")
        page.wait_for_selector(".app-shell")
        check("signed in after registering", "alice" in page.inner_text(".who"))
        check("empty library explains what to do", "Nothing here yet" in page.inner_text("#subjects"))

        page.fill("#subject", "Smoke Test")
        page.press("#subject", "Tab")
        page.set_input_files("#file-input", str(args.pdf))
        page.wait_for_selector(".job.done", timeout=240_000)
        check("upload finishes and reports passages", "Added" in page.inner_text(".job.done"))
        page.wait_for_selector(".doc .doc-title", timeout=15_000)
        check("document appears under its subject", "Smoke Test" in page.inner_text(".subject-head"))
        check("no server path leaks into the page", "uploads" not in page.content().lower())

        junk = args.out / "notes.txt"
        junk.write_text("not a supported file")
        page.set_input_files("#file-input", str(junk))
        page.wait_for_selector(".job.failed", timeout=10_000)
        check("unsupported file gets a friendly message", "only PDF" in page.inner_text(".job.failed"))
        page.click(".job.failed button")

        # ---- installable app
        if not context.service_workers:
            context.wait_for_event("serviceworker", timeout=15_000)
        check("the service worker is registered", any(w.url.endswith("/sw.js") for w in context.service_workers))
        manifest = json.loads(context.request.get(args.url + "/manifest.webmanifest").text())
        check("the app manifest is served", manifest["display"] == "standalone" and len(manifest["icons"]) >= 3)

        # ---- text question, follow-up, read aloud
        page.locator("#voice-bar label:has-text('Read answers aloud') input").check()
        check("voice options are shown", page.locator("#voice-bar").is_visible())
        good = ask(page, args.question)
        check("a question about the document gets an answer with a source", bool(good["answer"]) and bool(good["sources"]),
              good["answer"][:80].replace("\n", " "))
        check("the answer is not flagged as uncited or empty",
              not any("No source" in f or "did not write" in f for f in good["flags"]), str(good["flags"]))
        check("the chat is named after the first question", page.inner_text("#chat-title").startswith(args.question[:30]))
        heard = " ".join(spoken)
        check("the answer was read aloud without citation marks or Markdown",
              bool(heard.strip()) and "[" not in heard and "**" not in heard, heard[:90])
        page.screenshot(path=str(args.out / "answer.png"))
        cites = page.locator(".msg.bot").last.locator(".cite")
        if cites.count():
            cites.first.click()
            check("clicking a citation highlights its source", page.locator(".source.flash").count() >= 1)

        if args.follow_up:
            follow = ask(page, args.follow_up)
            check("a follow-up is searched with its context (shown to the user)", follow["searched"].startswith("Searched for"),
                  follow["searched"][:110])
            check("the follow-up gets an answer", bool(follow["answer"]) and not follow["refused"], follow["answer"][:80].replace("\n", " "))

        off_topic = ask(page, "What is the capital of France?")
        check("an off-topic question is refused without sources", off_topic["refused"] and not off_topic["sources"])

        # ---- saved chats
        user_bubbles = page.locator(".msg.user").count()
        page.click("#history summary")
        page.wait_for_selector(".history-item")
        check("the chat appears in History", page.locator(".history-item").count() == 1)
        page.click("text=New chat >> nth=-1")
        check("New chat starts empty", page.locator(".msg").count() == 0 and page.locator("#welcome").count() == 1)
        page.click("#history summary")
        page.click(".history-open")
        page.wait_for_selector(".msg.bot")
        check("reopening a saved chat restores every message", page.locator(".msg.user").count() == user_bubbles,
              f"{page.locator('.msg.user').count()} of {user_bubbles} questions")
        check("reopened answers keep their sources", page.locator(".msg.bot .source").count() >= 1)

        # ---- voice: the WAV is the microphone
        if args.voice_wav:
            check("the microphone button is available", page.locator("#mic").is_visible() and page.locator("#mic").is_enabled())
            users_before, bots_before = page.locator(".msg.user").count(), page.locator(".msg.bot").count()
            page.click("#mic")
            expect(page.locator("#mic")).to_have_class(re.compile("listening"), timeout=15_000)
            check("recording starts (the microphone button shows it is listening)", True)
            expect(page.locator(".msg.user")).to_have_count(users_before + 1, timeout=90_000)  # stops on silence, transcribes, sends
            heard_question = page.locator(".msg.user").last.inner_text()
            check("the spoken question was recognised and asked", len(heard_question.split()) >= 4, heard_question)
            voice_answer = finish_of(page, bots_before, 180_000)
            check("a spoken question gets a cited answer", bool(voice_answer["answer"]) and not voice_answer["refused"],
                  voice_answer["answer"][:80].replace("\n", " "))

        page.screenshot(path=str(args.out / "chat-history.png"))

        # ---- the computer being off (the phone's most common problem)
        context.set_offline(True)
        page.reload()
        page.wait_for_selector(".auth-card")
        check("with the server unreachable, the app says so instead of a browser error",
              "Can’t reach StudyBot" in page.inner_text(".auth-card"))
        context.set_offline(False)
        page.click("button:has-text('Try again')")  # not text=: that also matches the sentence "...then try again."
        page.wait_for_selector(".app-shell", timeout=20_000)
        check("it recovers when the server is back", page.locator(".app-shell").count() == 1)

        # ---- sign out / in, delete
        page.click("text=Sign out")
        page.wait_for_selector(".auth-card")
        page.fill("#username", "alice")
        page.fill("#password", "wrong password here")
        page.click("button[type=submit]")
        page.wait_for_selector(".error-text:not(:empty)")
        check("wrong password is rejected", "Wrong username or password" in page.inner_text(".error-text"))
        page.fill("#password", PASSWORD)
        page.click("button[type=submit]")
        page.wait_for_selector(".doc .doc-title")
        check("the library is still there after signing back in", page.locator(".doc").count() == 1)

        page.click("#history summary")
        page.wait_for_selector(".history-item")
        page.once("dialog", lambda d: d.accept())
        page.click(".history-item button:has-text('Delete')")
        page.wait_for_selector("text=No saved chats yet")
        check("a saved chat can be deleted", page.locator(".history-item").count() == 0)

        page.once("dialog", lambda d: d.accept())
        page.click(".doc button:has-text('Delete')")
        page.wait_for_selector("text=No documents yet", timeout=15_000)
        check("deleting a document removes it", page.locator(".doc").count() == 0)
        context.close()

        # ---- phone, dark theme. CSP is bypassed only here because reading layout needs page.evaluate.
        context, page = new_page(browser, viewport={"width": 390, "height": 844}, is_mobile=True, color_scheme="dark",
                                 bypass_csp=True)
        page.goto(args.url)
        page.fill("#username", "alice")
        page.fill("#password", PASSWORD)
        page.click("button[type=submit]")
        page.wait_for_selector(".app-shell")
        check("phone: tab bar is visible", page.locator(".tabbar").is_visible())
        check("phone: chat header, history and composer fit on screen",
              page.locator("#history summary").is_visible() and page.locator("#send").is_visible())
        page.click(".tabbar button[data-view=library]")
        check("phone: the library tab hides the chat", page.locator(".library").is_visible() and not page.locator(".chat").is_visible())
        check("phone: no horizontal page scroll", page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1"))
        page.click(".tabbar button[data-view=chat]")
        page.screenshot(path=str(args.out / "phone-chat.png"))
        browser.close()

    # HTTP error lines are expected: the weak-password (422) and wrong-password (401) checks cause them.
    real = [(k, t) for k, t in console_problems if "Failed to load resource" not in t]
    check("no Content-Security-Policy violations or script errors in the console", not real, json.dumps(real)[:300])
    failed = [name for name, ok in results if not ok]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed" + (f"; FAILED: {failed}" if failed else ""))
    print(f"screenshots: {args.out}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
