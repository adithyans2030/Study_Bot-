# Session 04: Phase 3, Chat and Voice

- **Date:** 2026-09-21
- **Phase:** 3 of 5 (see [PLAN.md](../../PLAN.md))
- **Outcome:** Phase 3 is **built and verified, but not fully closed.** StudyBot now remembers conversations, understands follow-up questions, listens to your voice (offline), can read answers aloud, and installs as an app. The **speed target is still missed** and voice on a phone has to wait for Phase 4 (section 9).
- **Tests:** 251 passing (83 new since Phase 2), plus a real-browser smoke test that passed **38/38** with the security policy enforced, including a spoken question played into the browser as a fake microphone.
- **Git:** committed locally with plain commit messages (no co-author or tool attribution). **Not pushed**; the Phase 2 commit is also still local. See section 10.

## 1. Summary

Phase 2 gave you a web page where each question stood alone. Phase 3 turns it into a study conversation:

- Ask "What is the difference between Sobel and Laplacian?", then just "Which one is more sensitive to noise?" and it knows what "one" means.
- Press the microphone, ask out loud, stop talking, and the question is typed, sent and answered by itself. The speech recognition runs on your PC; no audio leaves it and the recording file is deleted immediately.
- Tick "Read answers aloud" and the answer is spoken sentence by sentence while it is still being written.
- Every chat is saved and can be reopened or deleted from History.
- The page installs like an app (PC or phone) and shows a friendly screen when the PC is off.

## 2. What was built

| Area | Files (under `studybot/backend/`) | What it does |
|---|---|---|
| Saved chats | `app/core/conversations.py`, `app/api/conversations.py`, `app/rag/store.py` | New `conversations` and `messages` tables (database version 3). List, open and delete chats; each account only sees its own. Your question is saved before the model runs, the answer when it finishes. |
| Chat endpoint | `app/api/chat.py` | Now takes an optional `conversation_id`, creates one when missing, and streams a new leading `conversation` event, then `query` (only when the question was rewritten), `sources`, `token`, `done`. Refused answers are saved without sources. |
| Follow-ups | `app/rag/followup.py`, `app/rag/prompt.py`, `app/rag/pipeline.py` | A cheap rule detects questions that depend on the conversation ("it", "and PNG?", "which one..."). Only those are rewritten into a standalone question before search. The answering model also sees the last few exchanges, with an instruction to use them only to understand the question. |
| Voice in | `app/voice/audio.py`, `app/voice/stt.py`, `app/api/voice.py` | Checks the audio by its contents (webm, ogg, wav, mp4, mp3, flac), limits size (10 MB) and length (120 s), transcribes with faster-whisper `base.en` on the CPU, deletes the recording. |
| Warm-up | `app/main.py` | Loads the embedding model, the speech model and the language model in the background at start-up so the first question is not slow. |
| App shell | `app/static/manifest.webmanifest`, `sw.js`, `icons/` | Installable app with icons; the service worker caches only the page files (never `/api/`, so no answers or accounts are ever stored by it). |
| Interface | `app/static/app.js`, `rich.js`, `index.html`, `style.css` | History and New chat buttons, microphone with silence auto-stop, speaking indicator, voice picker, "Read answers aloud", "Send automatically after speaking", offline screen. `rich.js` gained the sentence splitter used for read-aloud. |
| Evaluation | `eval/followups.jsonl`, `eval/run_followups.py` | 18 two-turn conversations (14 follow-ups, 4 independent questions) to compare follow-up strategies without running the language model. |
| Tests | `tests/test_conversations.py`, `test_api_conversations.py`, `test_followup.py`, `test_voice.py`, `test_pwa.py`, `tests/js/rich.test.mjs`, `e2e/ui_smoke.py` | See section 7. |
| Dependencies | `requirements.txt`, `requirements.lock` | Added `faster-whisper`; lock file regenerated (62 pins, `pip check` clean). |

## 3. Using it

1. Start the server (`scripts\run_dev.ps1`) and open <http://127.0.0.1:8000>. Sign in with your existing account.
2. **Text:** type a question. Ask a follow-up in the same chat. **New chat** starts fresh; **History** lists earlier chats.
3. **Voice:** press the microphone, speak, pause. The first use downloads the 148 MB speech model once (already done on this PC).
4. **Listen:** tick *Read answers aloud* and choose a voice (Windows offers David, Hazel and Zira).
5. **Install:** Chrome/Edge address bar "Install StudyBot" on the PC; "Add to Home screen" on a phone.

Settings (all optional, see `.env.example`): `STUDYBOT_FOLLOWUP_MODE` (`llm`, `concat`, `off`), `STUDYBOT_HISTORY_TURNS`, `STUDYBOT_VOICE_ENABLED`, `STUDYBOT_STT_MODEL`, `STUDYBOT_STT_THREADS`, `STUDYBOT_MAX_AUDIO_MB`, `STUDYBOT_MAX_AUDIO_SECONDS`.

## 4. Decisions, each backed by a measurement

### 4.1 How to understand a follow-up

Retrieval only sees the words it is given, so "its main limitation?" finds nothing useful on its own. Three strategies were compared on 18 two-turn conversations from your Computer Vision notes (search only, no answer generation; `python -m eval.run_followups`):

| Strategy | Follow-ups found (hit@4, n=14) | Independent questions (hit@4, n=4) | Extra time per question |
|---|---|---|---|
| `off`: search what was typed | 78.6% | 100% | 0 s |
| `concat`: prepend the previous question | 100% | **75%** (it drags the old topic in) | 0 s |
| `llm`: the model rewrites it | 100% | 100% | 0.86 s average |

**`llm` is the default**, with `concat` as the automatic fallback if the model call fails or returns nonsense. The rewrite is only attempted when the detector thinks the question depends on the conversation: it flagged 14 of 14 real follow-ups and 1 of 4 independent questions (that one costs about 1-2 s and is harmless). The rewrite is shown in the interface only when it differs from what you typed.

The set is small and I wrote it myself, so treat 100% as "no failures seen", not as a guarantee.

### 4.2 Speech recognition model

`base.en` (int8, CPU), measured again at the end of the session on four spoken questions:

| Spoken | Audio | Time | Heard |
|---|---|---|---|
| Difference between Sobel and Laplacian | 3.5 s | 1.8 s | "…Sobel and **Laplation**" |
| How RANSAC rejects outliers | 3.3 s | 1.1 s | "…**Ransack** rejects outliers" |
| Bicubic vs bilinear | 4.5 s | 1.1 s | exact |
| Structure from motion and epipolar geometry | 4.6 s | 1.4 s | exact |

Transcription costs 1-2 s. `small.en` was tried earlier: more accurate on rare terms but 5-8x slower on this CPU, so it was rejected and its download deleted. Search still finds the right notes despite misspellings (tested), and the recognised text is shown before it is sent, so a mishearing is visible. Giving Whisper a hint list of technical words made accuracy **worse** and was dropped.

### 4.3 Reading answers aloud

The plan said Piper. It was replaced by the browser's built-in `speechSynthesis`: Piper is GPL-3 and needs a voice engine packaged and shipped, whereas the browser voices are free, work offline on Windows, Android and iOS, and use none of the PC's scarce RAM. The trade-off is that voice quality depends on the device.

### 4.4 Voice transport

The plan said a WebSocket with server-side voice detection. Instead the browser records, notices 1.5 s of silence itself, and uploads one short clip. That saves a WebSocket, a detection library and interruption logic for a cost of roughly a second on a four-second question. The exit gate can be revisited if this feels slow on the phone.

## 5. Security and privacy

- Recordings are checked by their contents (not the file name), size-limited, given random names, and deleted as soon as they are transcribed, including when transcription fails. An undecodable clip returns a plain message that does not leak decoder internals or paths.
- Chats are stored per account and every read and delete is checked against the signed-in user; another account gets "not found".
- The service worker never caches `/api/`, so no answer, account or recording is stored by the app shell. The security policy (scripts only from the app itself) is unchanged and the smoke test ran with it enforced.
- Nothing in this phase talks to an external service.

## 6. Bugs found and fixed

| Found by | Problem | Fix |
|---|---|---|
| Tests | A method named `list` on the conversations class hid Python's `list` inside the class and crashed at import. | Renamed to `list_for_user`. |
| Tests | The new first `conversation` event broke older tests that assumed the first event was `sources`. | Tests now find events by name. |
| Follow-up eval | A 12-word self-contained question ("…choose its threshold…") was treated as a follow-up because it contained "its". | Pronoun triggers only count in questions of 10 words or fewer; "such" removed. |
| Follow-up eval | "Which one is more sensitive to noise?" was not detected. | Added "which one/of the two", "both", "either", "neither", "the former/latter/second…". |
| Real browser (visual) | The app did not fill the screen height. | `html, body, #app` now take 100% height; checked on desktop and phone sizes. |
| Smoke test | Clicked a paragraph instead of the "Try again" button; checked "recording" too early. | Precise selectors and waiting for the state. |
| Merge | A patch left stray lines inside the start-up warm-up function. | Repaired by hand; covered by tests. |
| Speech | A vocabulary hint made recognition worse. | Removed. |
| Model download | `huggingface_hub` cache used symlinks, which fail without Windows Developer Mode. | Download straight into a normal folder. |

## 7. Verification

- **Automated:** `scripts\test.ps1`, 251 passed (about 30 s on a quiet machine). New coverage: chat storage and ownership, follow-up detection and rewriting (including model failure), voice upload validation, service-worker and manifest rules, the read-aloud sentence splitter (14 Node tests in total).
- **Real browser (Chromium via Playwright), 38/38 checks:** sign-up, upload a PDF, ask, follow-up asked and answered in the same chat, an off-topic question refused with no sources, the answer read aloud without citation marks, chat appears in History and reopens with its sources, delete a chat, offline screen and recovery when the server is stopped and restarted, phone-sized layout, no console security-policy violations, and a **spoken question** (a recorded wav played as the microphone) transcribed exactly as "What does the minimum filter do to bright regions of an image?" and answered.
- **Your real data:** backed up first (`%LOCALAPPDATA%\StudyBot\backups\studybot.pre-phase3.20260921-192933.db`), then upgraded to database version 3. Row counts before and after were identical; integrity check and foreign-key check clean.

## 8. Behaviour to know about

- A follow-up costs about 1-2 s extra for the rewrite. In a running chat about a third of short independent questions also trigger it.
- The first question after start-up can be slower while the models load; `/api/ready` reports when they are.
- Voice is unavailable (the microphone is disabled with an explanation) if `faster-whisper` is missing or the model cannot be downloaded; typing still works.
- Read-aloud voices depend on the device and browser. Only Chromium (Chrome/Edge) was tested; Firefox and Safari were not.
- Your library now holds three subjects and 382 passages: your three Computer Vision PDFs (64 passages) and "Advanced Computer Vision with Python - Full Course" (318 passages, added through the dashboard; its captions are auto-generated, so some technical terms may be misspelled). The `mlops` subject is now empty. This accounts for the change from 324 passages last session.

## 9. Not done and open items

- **Speed gate still missed.** First text appears about 6-16 s after you ask (the graphics card reads prompts at roughly 130 tokens/s), against a target of under 3 s. Planned but **not started**: choosing the number of passages per question adaptively, reusing Ollama's prompt cache between turns, testing flash attention, and speaking a short "checking your notes" line so voice users are not left in silence.
- **Phone voice needs HTTPS.** Browsers block the microphone on plain `http://192.168.x.x`. Text chat and installing work; voice on the phone arrives with Tailscale HTTPS in Phase 4.
- Faithfulness (answer actually supported by the cited passages) is still only spot-checked; a larger, independently written question set is still to do.
- No interruption ("barge-in") while the answer is being spoken, other than unticking Read answers aloud.
- Scanned-PDF text recognition (OCR) and the Whisper fallback for YouTube videos without captions are not built.
- No password reset or account screen yet.
- Only Chromium tested; iPhone/Safari behaviour of the install and voice features is unverified.
- The GitHub contributors sidebar was left as is at your request.

## 10. Actions and decisions for you

1. **Approve pushing.** Two commits are local only: Phase 2 (session 3) and Phase 3 (this session). The history contains no Claude or co-author text; that is checked again before any push.
2. **Rotate the OpenWeather key.** The public repository still contains it in an old commit, so rotating is the only real fix.
3. Try the app: ask a question, then a follow-up, then use the microphone and "Read answers aloud", and tell me what feels wrong. Real use will point at the next fixes better than my test questions.
4. Optional: fix the Ollama certificate problem (blocks trying `llama3.2:3b` / `qwen2.5:3b`, which might be faster or better than `gemma2:2b`), and tell me whether the Unit 4 and Unit 5 Word notes should be added to the library.

## 11. Next session

- **Phase 3 close-out (speed):** adaptive passage count, prompt-cache reuse, flash-attention experiment, spoken filler; re-measure time to first text.
- **Phase 4, deploy:** start automatically with Windows, Tailscale HTTPS so the phone can use voice, backups, hardening. The exit gate is "restart the PC and ask a question from the phone".

## 12. Quick reference

```powershell
cd studybot
powershell -ExecutionPolicy Bypass -File scripts\run_dev.ps1     # app at http://127.0.0.1:8000
powershell -ExecutionPolicy Bypass -File scripts\test.ps1        # 251 tests

cd backend
$py = "$env:LOCALAPPDATA\StudyBot\venv\Scripts\python.exe"
& $py -m eval.run_followups                                      # compare follow-up strategies
& $py e2e\ui_smoke.py --help                                     # real-browser test options
```
