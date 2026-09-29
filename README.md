# StudyBot

Free, local-first RAG chatbot for students. See [PLAN.md](PLAN.md) for the full plan and status.

## Quick start (Windows, PowerShell)

```powershell
cd studybot
powershell -ExecutionPolicy Bypass -File scripts\setup.ps1   # venv in %LOCALAPPDATA%\StudyBot\venv
powershell -ExecutionPolicy Bypass -File scripts\test.ps1    # run tests
powershell -ExecutionPolicy Bypass -File scripts\run_dev.ps1 # API on http://127.0.0.1:8000
```

Check `/api/health` (liveness) and `/api/ready` (data dir, embedding model, Ollama, LLM pulled). API docs at `/docs`.

## Running for real, and keeping it backed up (Phase 4)

`run_dev.ps1` is for development (auto-reload, console visible). For everyday use:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\install_autostart.ps1     # start at every login, restart on crash
powershell -ExecutionPolicy Bypass -File scripts\install_backup_task.ps1  # back up the database nightly at 3 AM
```

Both register a per-user Task Scheduler task (no admin rights, no stored password — they only run
while you are logged in). Undo either with the same command plus `-Uninstall`. Logs land in
`%LOCALAPPDATA%\StudyBot\logs\` (`console.log` for start/stop events, `studybot.log` for the app's
own messages); backups land in `%LOCALAPPDATA%\StudyBot\backups\` (the 14 most recent are kept). You
can also run either script's underlying action by hand: `scripts\run.ps1`, `scripts\backup.ps1`.

## Use the web dashboard (Phase 2)

Start the server (`scripts\run_dev.ps1`) and open <http://127.0.0.1:8000>.

1. **Create the first account.** It becomes the owner. Any collections you built earlier with the
   command line are adopted into it automatically.
2. **Add material:** drop PDF, PowerPoint (`.pptx`) or Word (`.docx`) files, or paste a YouTube link
   (English captions). Indexing runs in the background with live progress.
3. **Ask:** answers stream in with numbered sources you can click. Tick a subject in the library to
   ask only about it. Anything not in your notes is refused rather than guessed.

More people: set `STUDYBOT_ALLOW_REGISTRATION=true` (sign-ups are closed after the first account).
Each account has its own private library. Behind HTTPS (e.g. Tailscale) also set
`STUDYBOT_COOKIE_SECURE=true`. Uploads are limited to `STUDYBOT_MAX_UPLOAD_MB` (default 100), the
file type is decided from its contents, and it is stored under a random name.

## Chat, voice and the phone app (Phase 3)

- **Conversations are remembered.** Every chat is saved (History button, New chat button). A follow-up
  such as "Which one is more sensitive to noise?" is rewritten into a standalone question before
  searching, so it finds the right notes. `STUDYBOT_FOLLOWUP_MODE` is `llm` (best, about 1-2 s extra
  on follow-ups only), `concat` (free, instant) or `off`.
- **Ask by voice.** Press the microphone, speak, and stop talking: after 1.5 s of silence the
  recording is sent, transcribed **offline on your PC** (faster-whisper `base.en`, about 1-2 s for a
  short question), shown to you, and asked. The recording is deleted right after. The first use
  downloads the 148 MB speech model once.
- **Hear answers.** Tick *Read answers aloud* under the question box and pick a voice; answers are
  spoken sentence by sentence as they stream, using your device's own voices (nothing is sent
  anywhere). Untick *Send automatically after speaking* if you want to check the transcript first.
- **Install it as an app.** In Chrome/Edge use *Install StudyBot*; on a phone use *Add to Home screen*.
  If the PC is off you get a "Can't reach StudyBot" screen instead of a blank page.
- **The microphone needs `http://localhost` or HTTPS.** It works on the PC now. It will not work from a
  phone over plain `http://192.168.x.x`; that is solved by HTTPS through Tailscale in Phase 4.

Browser smoke test (needs Playwright + Chromium, a fresh data folder, and Ollama running):
`python e2e/ui_smoke.py --url http://127.0.0.1:8766 --pdf C:\path\notes.pdf --question "..." --follow-up "..." --voice-wav C:\path\question.wav`
(38 checks; the wav is played to the browser as a fake microphone. See the script for setup.)

## Try it from the command line (Phase 1)

The command line works on the owner account's library (or `--user NAME`).

Run from `studybot\backend` with the venv's Python (`%LOCALAPPDATA%\StudyBot\venv\Scripts\python.exe`).

```powershell
python -m app.cli ingest "C:\path\Unit_1_Notes.pdf" -c computer-vision   # PDF, PPTX, DOCX
python -m app.cli ingest "https://www.youtube.com/watch?v=VIDEO_ID" -c my-course
python -m app.cli list
python -m app.cli search "difference between sobel and laplacian" -c computer-vision   # no LLM
python -m app.cli ask "How does RANSAC reject outliers?" -c computer-vision            # cited answer
```

Collections are subjects: a question only searches the collections you name with `-c`
(omit it to search everything). Re-running `ingest` on an unchanged file is a no-op; on a changed
file it replaces the old version atomically.

Supported now: `.pdf` (text-based; scanned PDFs are detected but OCR is not built yet), `.pptx`,
`.docx`, and YouTube videos **that have English captions**. Old `.ppt` / `.doc` must be re-saved as
`.pptx` / `.docx`.

## Measuring quality

```powershell
python -m eval.run_retrieval --min-tokens 80 --rerank --show-misses   # hit@k, MRR, gate calibration
python -m eval.run_llm --models gemma2:2b                             # answers, refusals, latency
python -m eval.run_followups                                          # follow-up strategies: off / concat / llm
```

The 81-question golden set is `backend/eval/golden.jsonl`; the source list is `eval/corpus.json`.
Your own PDFs go in `%LOCALAPPDATA%\StudyBot\eval_corpus\` (they are never committed).

## Layout

```
studybot/
├── PLAN.md                 # plan + status tracker
├── backend/
│   ├── app/
│   │   ├── ingest/         # loaders (pdf, pptx, docx, youtube), chunker
│   │   ├── rag/            # embed, store (SQLite+FTS5+vectors), retrieve, rerank, prompt, pipeline
│   │   ├── core/           # accounts, conversations, job queue + worker, uploads, security, Ollama client
│   │   ├── voice/          # audio checks, offline speech-to-text
│   │   ├── api/            # FastAPI routes: auth, library, jobs, chat, conversations, voice, health
│   │   ├── static/         # the app (index.html, app.js, rich.js, style.css, manifest, sw.js, icons/)
│   │   ├── cli.py
│   │   └── config.py
│   ├── eval/               # golden set + retrieval and LLM evaluation scripts
│   ├── e2e/                # real-browser smoke test
│   ├── tests/              # Python tests + tests/js (Node) for the answer renderer
│   ├── requirements.txt    # runtime deps (ranges)
│   ├── requirements-dev.txt
│   └── requirements.lock   # exact versions used by setup.ps1
├── scripts/                # setup / run_dev / test
└── docs/sessions/          # one work-done write-up per session
```

## Where data lives

Runtime data (database, uploads, model files, transcript cache, logs, backups) and the virtualenv
live in `%LOCALAPPDATA%\StudyBot`, **not** in the repo. The repo is under OneDrive, and OneDrive
sync corrupts live SQLite files, so the app refuses to start with `STUDYBOT_HOME` inside OneDrive.
Override with `STUDYBOT_*` variables or `backend/.env` (see `.env.example`).
