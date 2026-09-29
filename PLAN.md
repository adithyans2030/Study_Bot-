# StudyBot: Production Plan

A free, local-first RAG chatbot for students. Upload PDF, PPTX, DOCX and YouTube links to a dashboard, then ask questions by text or voice. It starts with the PC, and the phone connects as an installable web app (PWA).

> **Status tracker** lives at the bottom. Every session ends with a write-up in [docs/sessions/](docs/sessions/).

"Flawless" is not achievable for a RAG system. What this plan gives you is **measurable quality gates** (section 9), so problems show up in evals rather than in front of students.

## 1. Baseline findings (legacy Proton project)

| Finding | Consequence |
|---|---|
| Legacy app is **Flask + Flask-SocketIO**, not FastAPI. It has no REST API. | StudyBot is a new FastAPI service. |
| Legacy app is a PC-control voice assistant with **no RAG and no LLM** (Ollama was removed in commit `f0880ce`). | Nothing to reuse for retrieval. |
| The intent classifier scores about 0.05 for **every** input (47 classes, near-uniform). "what is a binary search tree" routes to `GET_WEATHER`. Threshold is 0.05. | It cannot route "command vs. study question". Proton will call StudyBot by default and only run device commands on explicit patterns. |
| Wake word uses `recognize_google` in a loop. | Online, unofficial, unreliable. Replace with offline STT / openWakeWord. |
| OpenWeather key was hardcoded in git (`assistant.py`). | **Rotate the key** (history still contains it). Code now reads `OPENWEATHER_API_KEY`. |
| Agent tools include `run_command`, `run_code`, `write_file`. | StudyBot must have **no system tools**: uploaded documents are untrusted input. |
| Project lives in OneDrive. | Live data and the venv live in `%LOCALAPPDATA%\StudyBot`. |

**Hardware:** i5-10300H, 7.9 GB RAM, GTX 1650 (4 GB VRAM). Consequences: 3B-class LLM (Q4, about 2 GB VRAM), embeddings on CPU, no Docker, embedded databases only. The installed `llama3.1` 8B does not fit in 4 GB VRAM.

## 2. Assumptions

- For you and a small group, **served from your PC**. The phone is a client.
- If you mean many concurrent students, the hosting phase changes: a GTX 1650 serves about 1-2 concurrent chats.
- A phone cannot run the server at boot. The PC must be on unless an always-on fallback is added (section 7).

## 3. Architecture

```
Phone PWA ──┐                       ┌─ Ollama (LLM, localhost:11434)
Laptop web ─┼─ HTTPS (Tailscale) ─▶ FastAPI ─┼─ Chroma (vectors) + SQLite (metadata, FTS5/BM25)
Proton overlay ┘  REST + SSE        │        └─ faster-whisper (STT) · browser voices (TTS)
                                    └─ Worker process: extract → chunk → embed → index
```

Proton stays a **voice client** that calls `/api/chat`. Its PC-control skills stay separate.

## 4. Free stack

| Layer | Choice | Notes |
|---|---|---|
| API | FastAPI + Uvicorn, Pydantic v2, SQLite | Native SSE and WebSocket. |
| LLM | Ollama, `llama3.2:3b` or `qwen2.5:3b` (Q4) | Choose the winner on the golden set. `gemma2:2b` is the baseline. |
| Embeddings | `bge-small-en-v1.5` via **fastembed (ONNX)** on CPU | Lighter than torch on an 8 GB machine. Swap to `multilingual-e5-small` if content is not English. |
| Search | **One SQLite file**: FTS5 (BM25) + vectors with exact numpy search, merged with RRF | Changed from Chroma (session 2): atomic re-ingest, one-file backup, no extra service or RAM. See "Deviations". |
| Reranker | MiniLM cross-encoder, top 30 to top 6 | Optional and off by default; see session 2 results. |
| PDF | PyMuPDF; OCR for scans (not built yet) | PyMuPDF is AGPL: fine for private use only. `pypdf` fallback dropped (unused). |
| PPTX / DOCX | `python-pptx` / `python-docx` | Slide = chunk unit; include speaker notes. |
| YouTube | `youtube-transcript-api`, then `yt-dlp` + faster-whisper | Store timestamps for `&t=` deep links. |
| STT | faster-whisper `base.en` (int8, CPU) | Replaces Google STT. `small.en` measured 5-8x slower for a small accuracy gain; see session 4. |
| TTS | Browser `speechSynthesis` (the device's own voices) | Changed from Piper (session 4): Piper is GPL-3 and would mean packaging a voice engine; the browser voices are free, offline on Windows/Android/iOS and cost the server nothing. edge-tts stays out (unofficial). |
| Wake word | openWakeWord (desktop overlay only) | Web app uses push-to-talk. |
| Frontend | Plain HTML/CSS/JS, no build step (served by FastAPI); becomes an installable PWA in Phase 3 | Changed from React + Vite + Tailwind (session 3): nothing to build or update, no npm supply chain, works under a strict Content-Security-Policy. |
| Remote access | Tailscale free tier (real HTTPS) | Phone browsers block the mic on plain `http://192.168.x.x`. |

**Free-forever core:** Ollama, faster-whisper, bge, SQLite, FastAPI, plain HTML/JS (all local). Google STT, edge-tts, the YouTube transcript API and cloud LLM free tiers are optional, because providers can change terms.

## 5. RAG design

- **Ingestion:** background jobs `pending → extracting → chunking → embedding → ready | failed`, progress over SSE. Dedupe by SHA-256; re-ingest replaces old chunks atomically.
- **Chunking:** structure-aware, about 500-800 tokens, 10-15% overlap, each chunk prefixed `Doc title › Heading`. PDFs by page/heading, PPTs by slide, YouTube by 60-90 s windows.
- **Organisation:** subject collections; retrieval filters on `user_id + collection_id`.
- **Query path:** rewrite follow-up → hybrid search (top 20-30) → optional rerank (top 5-6) → numbered-source prompt → streamed answer with `[n]` citations.
- **Guardrails:** low retrieval score → "That's not in your materials"; drop citations that don't map to a real chunk; document text is data, never instructions; "general knowledge" is a separate, labelled toggle (off by default).
- **API surface** (built in session 3, except voice):
  `GET /api/auth/status` · `POST /api/auth/register|login|logout` · `GET /api/auth/me` ·
  `GET|POST /api/collections` · `DELETE /api/collections/{id}` ·
  `GET /api/documents` · `POST /api/documents` (upload) · `POST /api/documents/youtube` · `GET|DELETE /api/documents/{id}` · `POST /api/documents/{id}/reindex` ·
  `GET /api/jobs` · `GET /api/jobs/{id}` · `GET /api/jobs/{id}/events` (SSE) · `POST /api/chat` (SSE) ·
  `GET /api/conversations` · `GET|DELETE /api/conversations/{id}` (session 4) ·
  `GET /api/voice/status` · `POST /api/voice/transcribe` (session 4) ·
  `GET /api/health` · `GET /api/ready`

### Deviations from the original plan (with reasons)

| Plan said | Now | Why |
|---|---|---|
| Chroma for vectors, SQLite for metadata | Everything in one SQLite file | Replacing a document is one transaction (no drift between two stores); backup is one file; no extra dependency or RAM. Exact search is instant at study-material scale. Behind `Store`, so it can be swapped if the corpus outgrows it. |
| sentence-transformers | fastembed (ONNX runtime) | No PyTorch on an 8 GB machine; faster start. Its `bge-small-en-v1.5` is a quantised build. |
| Chunks of 500-800 tokens | Target 320, max 420 (estimated tokens) | bge-small truncates input at 512 tokens, so longer chunks would lose their tail when embedded. |
| `pypdf` fallback | Not implemented | PyMuPDF opened every test file; add it back only if a real file needs it. |
| `llama3.2:3b` as default LLM | `gemma2:2b` for now | The `llama3.2:3b` download fails on this network (untrusted TLS certificate on Ollama's blob host). `gemma2:2b` is already installed. |
| Separate worker process | Worker runs inside the API process, one job at a time | A second process would load a second copy of the embedding model on an 8 GB machine. Jobs are stored in SQLite, so they survive restarts. Splitting it out later only means running `JobRunner` elsewhere. |
| Chat endpoint in Phase 3 | Streaming `POST /api/chat` built in Phase 2 | The dashboard needed it, and it was the place to fix "the streamed text can contain invalid citations": the final `done` event carries the cleaned text. |
| Voice over `WS /api/voice` with server-side VAD | The browser records, detects 1.5 s of silence itself, and uploads one clip to `POST /api/voice/transcribe` | Streaming partial transcripts add a WebSocket, a VAD dependency and barge-in logic for a saving of about a second on 4-second questions. Revisit if voice feels slow on the phone. |
| Piper TTS | Browser `speechSynthesis`, spoken sentence by sentence while the answer streams | See the stack table. |
| Rewrite follow-ups as a plan step | Rule-based detector, then the model rewrites only follow-ups (`STUDYBOT_FOLLOWUP_MODE=llm`) | Measured on 18 two-turn cases: searching the follow-up as typed finds the notes 79% of the time, `concat` and `llm` both 100%; `concat` hurts independent questions (75%) where `llm` does not (100%), for about 1-2 s on follow-ups only. |
| Open registration | The first account becomes the owner; later sign-ups are closed unless `STUDYBOT_ALLOW_REGISTRATION=true` | For a personal server, a stranger who finds the port should not be able to create an account. |

## 6. Voice

Browser mic (MediaRecorder) → silence detected in the browser (1.5 s) → `POST /api/voice/transcribe` → faster-whisper `base.en` on CPU → the transcript is shown and sent to the chat → the answer is spoken sentence by sentence by the browser's own voices while it streams. Stop/interrupt is the speaker toggle; true barge-in is not built. The microphone only works on `localhost` or HTTPS, so phone voice waits for Phase 4.

## 7. Startup and access

- **PC:** API and worker start via Task Scheduler (or NSSM) with restart-on-failure, installed by a `deploy/` script. The API waits for Ollama's `/api/tags`, then warms the LLM and embedding models. The server needs no interactive session because the mic lives in the browser/overlay.
- **Phone:** installs the PWA over Tailscale. If it must work with the PC off: an always-on spare machine, or a free cloud VM (Oracle Always Free ARM: slow for LLMs, availability hit-and-miss).

## 8. Production hardening

Local accounts with argon2 and HTTP-only cookies; per-user data isolation; uploads checked by magic bytes with size/page limits, UUID filenames and rate limits; locked-down CORS; no debug mode; structured logs; nightly SQLite + Chroma backup; pinned dependencies (`requirements.lock`); venv outside OneDrive.

## 9. Quality gates (proposed targets, to be measured on this hardware)

- Golden set of 60-100 questions from real student material, about 20% unanswerable.
- Retrieval hit@5 ≥ 85% (no LLM needed to measure).
- Faithfulness (answer supported by cited chunks) ≥ 90%: human spot-check + LLM judge.
- Correct refusal on ≥ 90% of unanswerable questions.
- Text time-to-first-token < 3 s; first voice audio < about 4 s.
- A pytest eval runs before any change to chunking, embeddings or prompts is accepted. UI thumbs up/down feeds new cases into the set.

## 10. Roadmap

| Phase | Time | Deliverable | Exit gate |
|---|---|---|---|
| **0. Cleanup** | 1-2 days | Rotate key, untrack personal data, remove junk, fix requirements, scaffold repo + venv, data outside OneDrive | Fresh install runs; tests pass |
| **1. Core RAG** | ~1 week | Loaders, chunker, indexer, hybrid retrieval, CLI, golden set + eval | hit@5 gate |
| **2. API + dashboard** | ~1 week | Job queue, auth, upload + YouTube UI, SSE progress | Upload → index → delete works end to end |
| **3. Chat + voice** | ~1 week | Streaming chat with citations, STT/TTS, PWA | Latency + refusal gates |
| **4. Deploy** | 3-4 days | Startup tasks, Tailscale HTTPS, backups, hardening | Reboot PC → ask a question from the phone |
| **5. Extras** | later | Proton as client, quizzes/flashcards, optional cloud LLM fallback | n/a |

## 11. Risks

| Risk | Mitigation |
|---|---|
| Only 8 GB RAM | One model loaded (`OLLAMA_MAX_LOADED_MODELS=1`), no Docker, embedded DBs |
| YouTube blocks / no captions | Whisper fallback |
| Scanned PDFs | OCR fallback |
| Small model hallucinates | Retrieval-score gate, citation validation, eval gate |
| PC off | Always-on fallback (section 7) |
| Prompt injection via documents | No tools in the chat path; documents treated as data |

## Status tracker

- [x] **Phase 0: Cleanup and foundations** (session 1, see [SESSION-01](docs/sessions/SESSION-01-phase0-foundations.md))
- [~] **Phase 1: Core RAG** (session 2, see [SESSION-02](docs/sessions/SESSION-02-phase1-core-rag.md)). Retrieval gate met (hit@5 98.5% hybrid, 100% with reranker; target 85%) and refusal gate met on the 81-question set (13/14 strict, 14/14 by reading). **Not fully closed:** the < 3 s first-token target is missed (about 10 s on this GPU), faithfulness is only spot-checked, the 3B model comparison is blocked by a network TLS problem, OCR and Whisper fallback are not built.
- [x] **Phase 2: API + dashboard** (session 3, see [SESSION-03](docs/sessions/SESSION-03-phase2-api-dashboard.md)). Exit gate met: upload → index → ask → delete works end to end, verified in a real browser (19/19 smoke checks) and by 168 automated tests. Known gaps: scanned-PDF OCR, a PDF page limit, no password reset or account management screen, the first-token latency from Phase 1 is unchanged.
- [~] **Phase 3: Chat + voice** (session 4, see [SESSION-04](docs/sessions/SESSION-04-phase3-chat-voice.md)). Built and verified in a real browser (38/38 smoke checks, 251 automated tests): saved conversations, follow-up understanding, offline voice input, read-aloud, installable PWA with an offline screen. **Not closed:** the latency gate (first token < 3 s, first audio < 4 s) is still missed because the GPU reads prompts at about 130 tokens/s, and voice on a phone needs HTTPS (Phase 4). Latency work (adaptive k, prompt caching, flash attention) is not started; refusal on a larger independently written question set is not measured.
- [~] **Phase 4: Deploy.** Auto-start (Task Scheduler at login, no admin needed) and nightly database backups (SQLite online backup API, 14 kept) are built and verified against the real server and real database; structured logging added. **Not done:** Tailscale HTTPS — the part that lets a phone reach StudyBot at all and unlocks the phone microphone — needs the user to install Tailscale and sign in (an account/GUI step); everything else in Phase 4 is blocked on that address being available.
- [ ] Phase 5: Extras

## Frontend rewrite (React)

Not part of the original phase plan — added after Phase 3 shipped, because the hand-rolled
plain-JS dashboard "looks very basic." Built on its own branch (`frontend-react`) so the working
Phase 0-3 site is never at risk; the FastAPI backend and its API are unchanged.

- **Stack:** Vite + React 19 + TypeScript, Tailwind CSS v4 + shadcn/ui (Radix primitives),
  TanStack Query, React Router, react-hook-form + zod, next-themes, Vitest + Testing Library,
  Playwright (added when real screens exist to test). Dev server proxies `/api` straight to the
  real backend (127.0.0.1:8000) instead of mocking a separate contract — the backend already
  exists and is tested. Terminology matches the backend: "Subject" → **Collection**, "Thread" →
  **Conversation**.
- **Scope decision (2026-09-22):** Quiz, Flashcards, Summaries, a "general knowledge" toggle and a
  pixel-level PDF source viewer were all considered and explicitly **dropped** — none exist in the
  backend today, and the user chose to focus the whole rewrite on making today's real features
  (chat, citations, library, voice, conversation history, PWA) excellent rather than build UI with
  nothing behind it.
- **Milestone A — tooling & design system (done, 2026-09-22):** project scaffolded; design tokens
  (light/dark, system-by-default with a manual override) as CSS variables under shadcn's own
  naming so every primitive works unmodified; every text/background token pairing checked
  programmatically against WCAG AA 4.5:1 (22/22 pass — `tokens.contrast.test.ts`); 24 core
  primitives added (button, input, dialog, sheet, command palette, etc.); dev-mode axe
  accessibility checks wired in; a `/` foundations page substitutes for Storybook (dropped as
  not worth the upkeep for one developer). Verified: `tsc --noEmit` clean, lint clean (only
  known shadcn-vendor fast-refresh warnings), 22/22 unit tests pass, production build succeeds
  (153 KB gzipped JS — inside the 180 KB budget, though that's one route; watch this as more
  routes are added), and the dev proxy was confirmed live against the real `/api/health`.
- **Milestone B — auth (done, 2026-09-23):** login/register wired to the real `/api/auth/*`
  endpoints; registration-closed, offline, and route-guard states all real (no dead UI). Bundle
  budget re-verified after route-level code splitting: 166.7 KB gzip for `/login`, 170.2 KB for
  `/app` (both under the 180 KB target), 190.8 KB for `/register` (over, but a one-time setup
  visit the budget doesn't name).
- **Milestones C-F — library, chat, voice, PWA (done, 2026-09-23):** collections dashboard and
  document manager with live SSE indexing progress; chat with real `POST /api/chat` SSE streaming,
  citations, follow-ups, conversation history; voice input (silence auto-stop, ported from the
  plain-JS dashboard) and read-aloud; installable PWA (`vite-plugin-pwa`, `NetworkOnly` for `/api/`
  preserved). Full details and the stack decisions in the commit message (`git log`).
  **Verified against a real backend, real Ollama and real faster-whisper** (not just unit tests,
  which mock fetch): register → upload a real PDF → index → ask → citation → follow-up → voice
  (fake-mic WAV) → read-aloud → theme → logout/login → phone width → offline screen, repeated
  across ten fresh-backend runs while real bugs were found and fixed live — a crash on every new
  chat (bad optional chaining), a dev-proxy CSRF mismatch (fixed via `STUDYBOT_ALLOWED_ORIGINS`,
  not code), no way to navigate from chat back to the library (so no way to sign out), a missing
  theme toggle on the chat page, stale state on "New chat", a contrast failure axe caught, and a
  disabled dropzone with no explanation. 81 frontend tests, typecheck and lint all clean; 258
  backend tests unaffected (no backend changes this whole rewrite).
- **Milestone G — not started:** port the 38-check Playwright smoke test to the new app, a
  real accessibility/performance pass, docs, and the actual cutover (replacing the plain-JS
  dashboard the real server currently uses).
