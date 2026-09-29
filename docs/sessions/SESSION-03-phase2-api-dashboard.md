# Session 03: Phase 2, API and Dashboard

- **Date:** 2026-09-21
- **Phase:** 2 of 5 (see [PLAN.md](../../PLAN.md))
- **Outcome:** Phase 2 is **complete and verified**. You can sign in, add files or YouTube links, watch them index, ask questions and delete material, all from a web page. The exit gate ("upload, index, delete works end to end") is met and was checked in a real browser.
- **Tests:** 168 passing (71 new), plus a 19-check real-browser smoke test that passed 19/19 with the security policy enforced.
- **Git:** committed locally at the end of the session with plain commit messages (no co-author or tool attribution). **Not pushed**; see section 10.

## 1. Summary

The command-line tool from Phase 1 is now a web application. `scripts\run_dev.ps1` starts one server that provides the accounts, the upload and indexing queue, the streaming chat and the dashboard page. Your real index (2 subjects, 4 documents, 324 passages) was upgraded in place with nothing lost.

## 2. What was built

| Area | Files (under `studybot/backend/`) | What it does |
|---|---|---|
| Database | `app/rag/store.py` | Adds users, sessions and a job queue. Collections now belong to a user. Includes a safe upgrade of Phase 1 databases (section 4). |
| Accounts | `app/core/accounts.py`, `app/api/auth.py` | Sign up, sign in and out. Passwords hashed with argon2id, session tokens stored only as hashes, sign-in rate limiting. |
| Uploads | `app/core/uploads.py`, `app/api/library.py` | File type decided from contents, size limit enforced while streaming, zip-bomb check, random stored names, safe deletion. |
| Indexing queue | `app/core/jobs.py`, `app/core/worker.py`, `app/api/jobs.py` | Jobs live in SQLite and survive restarts. One background worker, live progress over Server-Sent Events. |
| Chat | `app/api/chat.py`, `app/rag/pipeline.py` | `POST /api/chat` streams sources, then text, then a final cleaned answer with flags. CLI and web share one code path. |
| Security | `app/core/security.py` | Cross-site request blocking, Content-Security-Policy and other browser headers. |
| Dashboard | `app/static/` (`index.html`, `app.js`, `rich.js`, `style.css`) | Sign-in, library, drag-and-drop upload with progress, streaming chat with clickable citations. Light and dark themes, works on a phone. |
| CLI | `app/cli.py` | Now works on the owner account's library (`--user NAME` for others). |
| Tests | `tests/`, `tests/js/`, `e2e/ui_smoke.py` | See section 7. |

Deviations from the plan (plain-JS dashboard instead of React, worker inside the API process, chat built now, closed registration after the first account) are in [PLAN.md](../../PLAN.md) with reasons.

## 3. Using it

1. Run `scripts\run_dev.ps1` and open <http://127.0.0.1:8000>.
2. **Create the first account.** It becomes the owner and automatically adopts the `computer-vision` and `mlops` collections you built from the command line.
3. Add files or a YouTube link, then ask questions. Ticking a subject narrows a question to it.

Others can have accounts only if you set `STUDYBOT_ALLOW_REGISTRATION=true`. Each account's library is private.

## 4. Protecting your real data

Adding owners to collections changed the database layout, and your index holds real work. So:

- A backup was taken first: `%LOCALAPPDATA%\StudyBot\backups\studybot.pre-phase2.20260921-122433.db`.
- The upgrade was tested on a Phase 1 database built in a test, then on a **copy** of your real one, then on the real one. Result each time: same counts (2 collections, 4 documents, 324 passages, 324 text-index rows), integrity check `ok`, no foreign-key problems, and a real question still answered with correct citations afterwards.
- The upgrade is idempotent (opening the database again changes nothing).

## 5. Security

Built and covered by tests: private-by-default endpoints (401 without a session), per-user isolation (another user gets 404 for your documents, jobs and collections, and searches never return your passages), generic sign-in errors that do not reveal which usernames exist, rate limiting after 5 failed sign-ins, HttpOnly + SameSite cookies, cross-site POST blocking, Content-Security-Policy and `nosniff`/`X-Frame-Options` headers, file type checks by contents, size and zip-bomb limits, random stored names, error messages with no server paths, only YouTube links accepted (no arbitrary URL fetching), and a chat path with no tools so a hostile document cannot run anything.

**Not covered yet:** no CSRF token beyond SameSite cookies and the Origin check; no PDF page-count limit; rate limiting exists only for sign-in (not for chat or uploads); no password change or reset screen and no way for the owner to remove another user in the UI; over plain HTTP on a home network the cookie is not marked `Secure` (set `STUDYBOT_COOKIE_SECURE=true` behind HTTPS, which Phase 4 sets up).

## 6. Bugs found and fixed

| # | Problem | How it was found | Fix |
|---|---|---|---|
| 1 | An unreadable upload was **not deleted**. On Windows, a PDF that failed to open stays locked while the error is being handled (confirmed by experiment), and `load_pdf` never closed files at all. | API test | PDFs are closed after loading; cleanup runs after the error handling; deletion retries. |
| 2 | The error shown to the user for a bad file **contained a server file path** (from the PDF library's message). | Same test, after the fix above | Error text no longer includes library messages, and shows your own file name instead of the stored random one. |
| 3 | The queue's wake-up signal was not thread-safe, so a new job could wait for the next poll. | Code review | Uses `call_soon_threadsafe`. |
| 4 | The OneDrive safety check **blocked any folder whose name merely contained the word**. | Starting a real server in a test folder | Now checks real OneDrive locations (folder names starting with "OneDrive", plus Windows' own environment variables). |
| 5 | A long data folder makes the embedding model fail to download (Windows 260-character path limit), and the user only saw "something went wrong". | Real-server run | Startup rejects a too-long `STUDYBOT_HOME` with advice, and `/api/ready` now reports if the embedding model cannot load. |
| 6 | The "Reading your notes…" line **never went away** after an answer. My CSS `display: flex` overrode the browser's `hidden` attribute. | Real-browser test | A global `[hidden]` rule. |
| 7 | A refused answer still showed "4 other passages considered" underneath. | Real-browser test | Not shown for refusals. |
| 8 | The first page load logged a 401 error in the browser console. | Real-browser test | The public status call now also says who is signed in. |
| 9 | `crypto.randomUUID()` (used for notices) does not exist on plain-HTTP pages, which would have broken the dashboard on a home network. | Code review | Replaced with a counter. |
| 10 | The test suite slowed from 8 s to 161 s because every app start loaded the real embedding model. | Test timing | Warm-up is off in tests (`warm_on_start`). |

## 7. Verification

- **168 automated tests** pass, including: the database upgrade, accounts and sessions, the queue (claim order, restarts, retry limit), upload safety, every API endpoint, per-user isolation, the chat stream, the CLI with accounts, and 9 JavaScript tests of the answer renderer (including "HTML in a model's answer stays literal text").
- **Real-browser smoke test, 19/19:** registers, uploads your actual Unit 2 PDF (19 passages), rejects a `.txt`, asks a real question through Ollama (answer with a clickable source), refuses an off-topic question, signs out and in again, deletes the document, checks the phone layout (bottom tabs, no sideways scrolling), and confirms the browser console has **no security-policy violations or script errors** with the policy enforced. It found bugs 6-8 above. It is saved as `e2e/ui_smoke.py`.
- Screenshots reviewed by eye for the desktop (light) and phone (dark) layouts.
- The smoke test ran on throwaway data folders (moved to the Recycle Bin afterwards); your real library was not used for it.

## 8. Behaviour to know about

- **The model still sometimes cites a source that does not exist** (it did in the browser test). The page removes those markers and shows "Removed 1 reference to sources that do not exist." Uncited answers and empty answers are flagged too.
- **Speed is unchanged from Phase 1:** about 6-16 seconds to the first word on this GPU, longer for video answers. The page shows a running "Reading your notes… 7s" so it does not look frozen. The real fix is Phase 3 work.
- First start downloads the embedding model (about 20 seconds; the Hugging Face library logs a harmless symlink error on Windows first. Turning on Windows Developer Mode removes that noise).

## 9. Not done and open items

- OCR for scanned PDFs; a PDF page limit; Whisper fallback for videos without captions.
- Account management (change password, remove a user).
- Only tested in Chromium. Not yet tried in Firefox or Safari, on a real phone, or with a screen reader (normal semantic elements and labels are used, but that is not a test).
- The `llama3.2:3b` download problem (untrusted certificate on this network) still blocks comparing 3B models.
- The GitHub contributors sidebar (see the previous session's note) has not been re-checked.

## 10. Actions and decisions for you

1. **Start the server and create your account** (section 3). Use a password you will remember; there is no reset screen yet.
2. **Rotate the OpenWeather key.** The repository is public and the key is still in its first commit.
3. **Approve pushing** this session's commit to GitHub (I have only committed it locally).
4. Optional: fix the Ollama certificate problem, and turn on Windows Developer Mode to silence the model-download log noise.

## 11. Next session: Phase 3, chat and voice

1. Conversations that remember earlier questions, with follow-up questions rewritten so search still works ("and what about the second one?").
2. Voice: speech in (faster-whisper, offline), speech out (Piper, offline), with push-to-talk in the browser.
3. Make it an installable phone app (PWA).
4. Speed: fewer or better-chosen passages, reusing Ollama's prompt cache, and a spoken "checking your notes" line so voice users are not left in silence.
5. Larger, independently written test questions to measure faithfulness properly.

## 12. Quick reference

```powershell
cd studybot
powershell -ExecutionPolicy Bypass -File scripts\run_dev.ps1     # web app at http://127.0.0.1:8000
powershell -ExecutionPolicy Bypass -File scripts\test.ps1        # 168 tests

cd backend
$py = "$env:LOCALAPPDATA\StudyBot\venv\Scripts\python.exe"
& $py -m app.cli list                                            # your library (owner account)
& $py -m app.cli ask "How does RANSAC reject outliers?" -c computer-vision
```
