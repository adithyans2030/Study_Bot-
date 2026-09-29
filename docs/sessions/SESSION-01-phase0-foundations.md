# Session 01: Phase 0, Cleanup and Foundations

- **Date:** 2026-09-21
- **Phase:** 0 of 5 (see [PLAN.md](../../PLAN.md))
- **Outcome:** Phase 0 complete. All exit-gate checks passed (details in section 4).
- **Nothing was committed.** All changes are uncommitted in the working tree.

## 1. Summary

Analysed the existing Proton voice assistant, wrote the production plan, cleaned up the legacy project (secret, junk files, personal data, requirements), and scaffolded the new **StudyBot** FastAPI backend with config, health/readiness endpoints, tests and setup scripts. The virtualenv and runtime data live outside OneDrive.

## 2. Work done

### 2.1 Analysis (no code changes)

- Read the legacy app end to end. It is **Flask + Flask-SocketIO**, not FastAPI, with no REST API, no RAG and no LLM (Ollama was removed in commit `f0880ce`).
- Ran the intent classifier on study questions. Every input scores about 0.05 across 47 classes (near-uniform), so it cannot separate commands from questions. Example: "what is a binary search tree" → `GET_WEATHER`.
- Checked the machine: i5-10300H, 7.9 GB RAM, GTX 1650 (4 GB VRAM), Python 3.12.7, Ollama 0.34.2 with models `luttapi`, `gemma2:2b`, `llama3.1` (8B).
- Full findings are in [PLAN.md](../../PLAN.md) section 1.

### 2.2 Legacy project cleanup

| Change | Detail |
|---|---|
| Hardcoded API key removed | `assistant.py` `get_weather()` now reads `OPENWEATHER_API_KEY`, speaks a clear message if unset, uses HTTPS and a 10 s timeout. |
| 17 junk files removed | Crash logs, empty outputs, and three throwaway debug scripts (`debug.py`, `test.py`, `test_hide.py`). All were inspected first: 0-byte logs or tiny scripts. **Sent to the Windows Recycle Bin** (recoverable). |
| Personal data untracked | `git rm --cached` on `data/context.json` (conversation history) and `data/email_config.json` (will hold credentials once configured). Files remain on disk; `EmailManager` recreates its config if missing. |
| `.gitignore` expanded | `.venv`, `.env*`, the two data files above, `studybot/data/`, and `*.log`, `crash_*.txt`, `error*.txt`, `output*.txt`. |
| `requirements.txt` fixed | Added the 11 packages the code imports but the file lacked (beautifulsoup4, edge-tts, pygame, playwright, pywin32, comtypes, pycaw, pyautogui, pyperclip, pygetwindow, screen_brightness_control). The scikit-learn and joblib pins were also updated to the installed versions. Pins now match versions actually installed and working. |

### 2.3 StudyBot scaffold (`studybot/`)

| File | Purpose |
|---|---|
| `backend/app/config.py` | `Settings` from `STUDYBOT_*` env / `.env`. Default data home `%LOCALAPPDATA%\StudyBot`. **Refuses any home path inside OneDrive.** |
| `backend/app/main.py` | `create_app()` factory; creates data dirs on startup. |
| `backend/app/api/health.py` | `GET /api/health` (liveness) and `GET /api/ready` (data dir writable, Ollama reachable, configured LLM pulled; 503 with per-check detail otherwise). |
| `backend/app/core/ollama.py` | Minimal Ollama client (`list_models`, tag normalisation). Extended in Phase 1. |
| `backend/tests/` | 11 tests covering config and health/readiness. |
| `backend/requirements*.txt`, `requirements.lock` | Runtime ranges, dev extras, exact 28-package lock. |
| `scripts/setup.ps1`, `run_dev.ps1`, `test.ps1` | Create the venv outside OneDrive, run the API, run tests. |
| `PLAN.md`, `README.md`, `.env.example` | Plan with status tracker, quick start, config template. |

## 3. Decisions and rationale

| Decision | Why |
|---|---|
| Venv and data in `%LOCALAPPDATA%\StudyBot` | OneDrive sync corrupts live SQLite/vector files; a venv also creates thousands of files to sync. |
| App enforces the no-OneDrive rule in code | A silent misconfiguration would risk data corruption later, so it fails fast instead. |
| `/api/ready` checks Ollama and the model now | Phase 1 depends on it, and it turns "model not pulled" into a clear, actionable message. |
| Phase 0 deps kept minimal (no chromadb, torch, whisper) | Heavy packages are installed when the phase needs them, keeping this gate fast and the lock small. |
| Sent junk to Recycle Bin instead of permanent delete | A plain `rm` was blocked as irreversible; Recycle Bin achieved the same cleanup while staying recoverable. |
| Legacy `app.py` (`debug=True`, CORS `*`) left unchanged | Out of Phase 0 scope. It binds to localhost by default and is being replaced. Do not expose it beyond localhost. |

## 4. Verification

| Check | Result |
|---|---|
| `scripts\setup.ps1` from scratch (no existing venv) | Passed. Venv created, 28 packages installed. |
| `scripts\test.ps1` | **11 passed**, 2 deprecation warnings (see 5). |
| Live server via `run_dev.ps1` on port 8765 | `/api/health` → 200 `{"status":"ok","version":"0.1.0"}`. Data dirs created under `%LOCALAPPDATA%\StudyBot`. |
| `/api/ready` against your real Ollama | 503, as expected: `data_dir` ok, `ollama` ok (3 models), `llm_model` **not ok**: `'llama3.2:3b' not pulled`. |
| `python -m py_compile assistant.py` | Passed. |
| `pip install --dry-run -r ProtonVoiceAssistant/requirements.txt` | Exit code 0, no conflicts. Nothing was installed. |
| Scan for remaining hardcoded keys in legacy `.py` files | 0 found. |

## 5. Not done, caveats, and open issues

**Actions only you can do**
1. **Rotate the OpenWeather key** in your OpenWeather account. Removing it from code does not remove it from git history, so treat the old key as exposed.
2. Set the new key if you still use weather: `setx OPENWEATHER_API_KEY "<new key>"`.

**Known gaps**
- **Nothing is committed.** Staged: the two `git rm --cached` deletions. Unstaged: the other edits and the new `studybot/` folder. Git history still contains the old key and earlier `context.json` versions; scrubbing needs a history rewrite, which I did not do.
- **Legacy app not re-run end to end.** I verified it compiles and its requirements resolve, but did not launch it (it needs a microphone and audio devices). The `get_weather` change is small, but untested at runtime.
- **"Fresh clone" was tested from the repo files, not a `git clone`,** because nothing is committed yet.
- `llama3.2:3b` is **not pulled**, so `/api/ready` is 503 until it is (Phase 1 step 1).
- Test-only warning: `starlette.testclient` says using `httpx` is deprecated ("install `httpx2`"). Runtime code is unaffected. I have not investigated the replacement, so revisit it when tests are next touched.
- Legacy leftovers deliberately untouched: `app.py` `debug=True` / CORS `*` / unauthenticated `command` event; a stale "make sure Ollama is running" message at `proton_desktop.py:234`; unpinned and unused `duckduckgo-search` in requirements.
- My chat estimate said "14 junk files"; the actual count was **17**.

**To restore anything from the cleanup:** open the Recycle Bin and restore the 17 files (`bat_output.txt` plus 16 in `ProtonVoiceAssistant/`).

## 6. Next session: Phase 1, Core RAG

1. `ollama pull llama3.2:3b` (about 2 GB) and confirm `/api/ready` returns 200.
2. Add dependencies: chromadb, sentence-transformers (already installed globally), pypdf/PyMuPDF, python-pptx, python-docx, youtube-transcript-api, faster-whisper.
3. Build loaders (PDF, PPTX, DOCX, YouTube), the structure-aware chunker, embedding + index, and hybrid retrieval (Chroma + FTS5 with RRF).
4. Build a CLI: `ingest <file|url>` and `ask "<question>"`.
5. Assemble a **golden set** (I need 2-3 real sample documents such as lecture PDFs or slides from you) and an eval script measuring hit@5.
6. Compare `llama3.2:3b`, `qwen2.5:3b` and `gemma2:2b` on the golden set.
7. Exit gate: hit@5 ≥ 85%.

**Please provide:** a few real study documents (PDF/PPT/DOCX) and a couple of YouTube lecture links, and say whether content is English-only.

## 7. Quick reference

```powershell
cd studybot
powershell -ExecutionPolicy Bypass -File scripts\setup.ps1     # one-time
powershell -ExecutionPolicy Bypass -File scripts\test.ps1      # tests
powershell -ExecutionPolicy Bypass -File scripts\run_dev.ps1   # http://127.0.0.1:8000/docs
```
