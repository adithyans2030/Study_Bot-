# Session 02: Phase 1, Core RAG

- **Date:** 2026-09-21
- **Phase:** 1 of 5 (see [PLAN.md](../../PLAN.md))
- **Outcome:** Phase 1 is **built and largely met, but not fully closed.** The retrieval and refusal targets are met on the test set. The latency target is **missed**, faithfulness is only spot-checked, and the 3B-model comparison is blocked (section 9).
- **Git:** Phase 0 and Phase 1 are both on GitHub `main`. At your request, the automatically added co-author line was removed from both commit messages and the history was force-pushed (see section 3). Current head: `0475cbf` plus a small follow-up commit for these notes.
- **Tests:** 97 passing (`scripts\test.ps1`).

## 1. Summary

You can now ingest PDF, PPTX, DOCX files and YouTube videos into subject collections, search them with a hybrid semantic + keyword search, and ask questions that are answered with citations, or refused when the answer is not in your materials. Everything runs locally and free. It is used from a command line for now; the API and dashboard are Phase 2.

## 2. What you sent, and what it turned out to be

| Input | Finding |
|---|---|
| 3 PDFs (Computer Vision Units 1-3) | Found in `Downloads`; copied to `%LOCALAPPDATA%\StudyBot\eval_corpus\`. Text-based PDFs with headings, bullets, 10 tables. All ingest cleanly (64 chunks). |
| YouTube link `tVskbekONlw&list=PPSV` | **Not a Computer Vision video.** It is freeCodeCamp's 5.5-hour *"Learn MLOps with MLflow and Databricks"* (auto-generated English captions, 260 chunks). The `list=PPSV` playlist part was ignored. I used it as a second subject ("mlops"), which also tests that subjects stay separate. **If you meant a different link, send it.** |
| Not used | `Computer_Vision_Unit_4_...docx` and `Unit_5_...docx` (and `.docx` copies of 1-3) also exist in your Downloads, but you did not share them, so I did not read them. |

## 3. GitHub push

- Pushed the Phase 0 commit `4cd1db6` to `origin/main` (fast-forward, no force).
- **The repository is public, and the original commit `d5fa17b` already contains the OpenWeather key on GitHub.** My push did not add any exposure, but the key is public. **Rotate it now** (see section 10). Old `context.json` versions (your earlier assistant conversation history) are also in the public history.

**Removing the extra contributor (done later the same day, at your request).** My commit messages ended with an automatically added `Co-Authored-By` line, which is what makes GitHub credit a co-author. I removed that line from the two affected commits and force-pushed:

| | Before | After |
|---|---|---|
| Phase 0 commit | `4cd1db6` | `0508b44` |
| Phase 1 commit | `7f55046` (local) | `0475cbf` |

- Only the commit messages changed. File contents are byte-for-byte identical, and authors and dates are unchanged. The three older commits never had the line.
- The push used `--force-with-lease` pinned to `4cd1db6`, so it could only overwrite that exact commit. The repo had 0 forks.
- GitHub's API and Insights graph now list one contributor, `adithyans2030`, and no commit message on `main` has a co-author line.
- **Not yet resolved on the website:** the repository page's *Contributors* sidebar still showed the removed co-author ("Contributors 2") when checked afterwards. That list is a separate GitHub-side cache that had not refreshed, and nothing in the repository still references it (the remote has only `main`, no pull-request refs). Options: wait and re-check, ask GitHub Support to purge the old commit and refresh that cache, or delete and recreate the repository.
- **Limitation:** the old commit `4cd1db6` is no longer on any branch, but GitHub still serves it by its exact hash (HTTP 200) until its own cleanup runs. Only someone with that link could see it. To have it purged sooner, ask GitHub Support to remove unreferenced commit `4cd1db6a8add81821c7e8c661fcae327991aa55d` from `adithyans2030/Proton_Voice-`.
- Going forward, commits carry no co-author or tool attribution.

## 4. What was built

| Area | Files (under `studybot/backend/`) | Notes |
|---|---|---|
| Loaders | `app/ingest/pdf_loader.py`, `pptx_loader.py`, `docx_loader.py`, `youtube_loader.py`, `loader.py` | PDF: headings from font size/weight, bullets, tables rendered as self-describing rows, page footers removed. PPTX: one segment per slide incl. speaker notes. DOCX: Heading styles + tables. YouTube: captions (cached on disk), title via oEmbed, timestamps kept. |
| Chunker | `app/ingest/chunker.py` | Section-aware; long sections split with overlap; tiny sections merged; slides one per chunk; transcripts in ~90 s windows. Each chunk has a "Document > Heading" header. |
| Store | `app/rag/store.py` | One SQLite file: documents, chunks, FTS5 index, vectors. Re-ingest replaces a document in one transaction. |
| Retrieval | `app/rag/embed.py`, `retrieve.py`, `rerank.py` | bge-small (fastembed, CPU); dense + BM25 merged by reciprocal rank fusion; optional cross-encoder reranker. |
| Answering | `app/rag/prompt.py`, `pipeline.py`, `app/core/ollama.py` | Numbered-source prompt, citation extraction/validation, refusal detection, content-free-answer detection, streaming Ollama client. |
| CLI | `app/cli.py` | `ingest`, `search`, `ask`, `list`, `delete`. |
| Evaluation | `eval/golden.jsonl`, `corpus.json`, `run_retrieval.py`, `run_llm.py` | 81 questions (67 answerable, 14 not in the materials). |

Design deviations from PLAN.md (single SQLite instead of Chroma, fastembed instead of sentence-transformers, smaller chunks, no `pypdf` fallback, `gemma2:2b` default) are listed with reasons in [PLAN.md](../../PLAN.md).

## 5. Bugs found and fixed this session

| # | Bug | How it was found | Fix |
|---|---|---|---|
| 1 | The chunker **silently dropped the last small block** of a long section. | A test that checks every input word survives chunking. | Track overlap vs new text separately. |
| 2 | Test PDFs were missing their headings (text boxes too small, silently not drawn). | Loader tests failed. | Fixture now asserts every box fits. |
| 3 | **Tables were placed at the top of their page**, under the wrong heading, because PyMuPDF lists the footer first. | Reading real chunks by eye. | Place tables after the last line above them. Regression test added and confirmed to fail on the old code. |
| 4 | The eval's "reranker" row **silently did nothing** (no reranker was configured). Its numbers were identical to plain hybrid. | Suspiciously identical results. | Requesting rerank without a reranker now raises an error. Earlier rerank numbers were discarded. |
| 5 | A transient Ollama timeout **killed a 20-minute eval** and lost all 24 answers. | The run crashed. | Friendly `OllamaError`, longer connect timeout, retries, results saved per question, `--resume`. |
| 6 | Twice a shell `\| tail` / `\| grep` **hid a failure** (a failed model download; a crashed eval reported "exit code 0"). | Reading the raw output. | Stopped piping long jobs; results now carry their own status. |

One eval run (24 of 81 answered) and two earlier retrieval runs were discarded because of bugs 3-5; **all numbers below are from runs after the fixes.**

## 6. Results

### 6.1 Retrieval (no LLM). 67 answerable questions, chunk target 320 tokens

| Mode | hit@1 | hit@3 | hit@5 | MRR |
|---|---|---|---|---|
| dense only | 82.1% | 97.0% | 98.5% | 0.892 |
| BM25 only | 82.1% | 97.0% | 100% | 0.890 |
| **hybrid (default)** | 88.1% | 95.5% | 98.5% | 0.927 |
| hybrid + reranker | 91.0% | 100% | 100% | 0.953 |

- **Plan target hit@5 >= 85%: met** (98.5%).
- Hybrid beats either method alone on hit@1 and MRR, as the plan predicted.
- The reranker helps a little (about 2 questions at rank 1) **but costs 4.2 s per query on CPU vs 52 ms for hybrid**, so it is **off by default**.
- Chunk size sweep (target 150 / 220 / 320 tokens): hybrid MRR 0.910 / 0.929 / 0.927, a difference of about one question, so no change was made.
- The one retrieval miss (cv-08, "What is OCR...") is explained by chunking, which I checked: the OCR paragraph sits in one 239-word chunk that also holds eight other applications (healthcare, vehicles, surveillance, manufacturing, agriculture, retail, robotics, sports), so its meaning is diluted. Fix to try next: treat "Bold label: text" paragraphs as their own small sections. (Smaller chunk targets did not reliably fix it, because the merge step re-combines short paragraphs.)

### 6.2 "Not in your materials" gate

| Signal | Separates answerable from not (AUC) |
|---|---|
| cosine similarity (cheap, used) | 0.878 |
| reranker score (4 s per query) | 0.969 |

Cosine of the best match: answerable questions min 0.567 / median 0.770; unanswerable median 0.623 / max 0.796. The two ranges overlap, so **a score gate alone cannot decide**; it only catches clearly off-topic questions. Default set to **0.55** (falsely refuses 0 of 67 answerable; catches 1 of 14). The LLM does the rest. This threshold is **provisional** (only 14 unanswerable examples).

### 6.3 Answers with `gemma2:2b` (score gate bypassed to test the raw model; 6 chunks per question, the default at the time). All 81 questions

| Measure | Result |
|---|---|
| Right passage was in the model's context | 66/67 (99%) |
| Falsely refused an answerable question | 1/67 (1.5%), and it was a retrieval miss |
| Keyword-correctness proxy (of 66 answered) | 62/66 (94%) |
| Answers with a valid citation (of 66) | 60/66 (91%) |
| Refused questions that are not in the materials | 13/14 (93%) strict phrase match; **14/14 by reading**: the miss ("Unit 4?") answered "not covered in the provided study materials" |
| Median first token / total / generation | **10.0 s** / 12.3 s / 30 tok/s |
| Median prompt | 1,254 tokens at only **130 tok/s** |

**Human review of the failures and a random sample** (the keyword check is only a proxy):
- **cv-05 is a wrong answer**: it said the two segmentation types are "Region Growing" and "Active Contours" (your notes say semantic and instance). It mixed chunks from two units and cited nothing.
- **yt-08 is content-free**: the whole answer was `[2][5][6]`. A citation-only answer now sets `Answer.empty`.
- cv-27 is correct but incomplete; yt-07 is uncited and unverifiable; the other keyword "failures" were fine.
- 4 of 4 random answers I read were accurate, cited and concise.
- 6 of 66 answers (9%) had no valid citation.

**Final end-to-end check on your real index (defaults: 4 chunks, gate 0.55)** found two more problems the automated metrics did not:
- **An unfaithful detail that the keyword check would have passed.** Asked how to log one MLflow parameter, the model answered with a `mlflow.log_params({"learning_rate": 0.03})` code example. The video says `log_param` for one parameter and never shows that snippet, so the model added it itself. My keyword `log_param` matches inside `log_params`, so the proxy would have scored it correct. This is why the faithfulness gate stays **open**.
- **A nonexistent citation `[7]` appeared in the live-streamed text** (only 4 sources exist). Citations were cleaned in the source list but the stream is raw. The CLI now prints a warning; the Phase 2 API must send the cleaned final text and the dashboard should replace the streamed text with it.

The same check confirmed the good paths: the Sobel/Laplacian answer was correct and cited to Unit 2 p.3, the video answer linked to `https://www.youtube.com/watch?v=tVskbekONlw&t=2377s` (39:37), and the off-topic question ("capital of France") was stopped by the gate in 1.3 s without calling the model. Video answers are slower (16 s to first token) because transcript chunks are longer than PDF chunks.

### 6.4 Latency and how many chunks to send

The plan's target is under 3 s to first token. **It is missed by a wide margin**: the GTX 1650 processes the prompt at only about 130 tokens/s, so a 1,250-token prompt (6 chunks) takes about 10 s before the first word. The model already runs 100% on the GPU, so this is the GPU's speed, not CPU spill-over.

A follow-up test on 12 answerable questions varied how many chunks are sent to the model:

| Chunks sent | Median prompt | Median first token | Right passage in context | Keyword-correct | Cited |
|---|---|---|---|---|---|
| 6 | 1,282 tokens | 11.4 s | 12/12 | 12/12 | 12/12 |
| **4 (new default)** | 930 tokens | **6.4 s** | 12/12 | 12/12 | 11/12 |
| 3 | 666 tokens | 7.5 s | 12/12 | 12/12 | 11/12 |

`retrieve_k` now defaults to **4**. Caveats: only 12 questions, timings are noisy (one k=4 run took 18.7 s), and retrieval hit@3 was 95.5% vs 98.5% at hit@5, so a small recall cost is possible. It is configurable (`STUDYBOT_RETRIEVE_K`). Still to try in Phase 2/3: adaptive k (fewer chunks when the top match is strong), trimming chunks to their best sentences, reusing Ollama's prompt cache for the fixed system prompt, `OLLAMA_FLASH_ATTENTION`, and starting text-to-speech with a short "checking your notes" line so voice users are not left in silence. A smaller or faster model is the other lever.

## 7. Against the plan's quality gates

| Gate (proposed in PLAN.md) | Result | Status |
|---|---|---|
| Retrieval hit@5 >= 85% | 98.5% (hybrid) | Met |
| Correct refusal >= 90% of unanswerable | 13/14 strict, 14/14 by reading | Met |
| Faithfulness >= 90% | Not measured properly. Spot check found 1 clearly wrong answer in 66. | **Open** |
| Text first token < 3 s | **10.0 s median** | **Missed** |

## 8. How much to trust these numbers

- I wrote the 81 questions myself from the same notes, so the test is **easier than real student use**. The 5 casual "voice-style" questions are the harder part; they did fine but n=5.
- 67 answerable questions means **one question is 1.5 percentage points**. Differences smaller than that (reranker, chunk size) are noise.
- The corpus is small (64 note chunks), so hit@5 has a ceiling effect; hit@1 and MRR are the informative numbers.
- The video ground truth comes from auto-generated captions and time windows I chose by reading the transcript.
- Keyword checks and citation checks are cheap proxies. Faithfulness needs a human or a stronger judge model.
- Only `gemma2:2b` was evaluated with the LLM.

## 9. Environment problems found

| Problem | Detail | Needed from you |
|---|---|---|
| `ollama pull llama3.2:3b` fails | `x509: certificate signed by unknown authority` for Ollama's download host (`cloudflarestorage.com`). Windows reports `SEC_E_UNTRUSTED_ROOT`. Hugging Face and pip are fine. Likely an antivirus "HTTPS scanning" feature, or a college/ISP filter. I did **not** bypass certificate checks. | Try a different network (phone hotspot), or if an antivirus does HTTPS scanning, ensure its root certificate is trusted by Windows or exclude Ollama. Then `ollama pull llama3.2:3b` and `qwen2.5:3b`. |
| Low memory | With 7.9 GB RAM, running the reranker experiment during the LLM eval dropped free RAM to 0.3 GB and stalled both. | Nothing; run heavy jobs one at a time. |
| Slow prompt processing | The GTX 1650 processes prompts at about 130 tok/s. | See 6.4. |

## 10. Actions and decisions for you

1. **Rotate the OpenWeather key now.** The repo is public and the key is in its history.
2. ~~Approve pushing this session's commit~~ Done: pushed after removing the co-author line (section 3). Optional: ask GitHub Support to purge the old commit `4cd1db6`.
3. Fix the Ollama TLS problem, then I can compare `llama3.2:3b` and `qwen2.5:3b` (about 20 minutes each).
4. Confirm the YouTube link is what you wanted, and say whether to also ingest the Unit 4 and 5 `.docx` notes.

## 11. Not done (open items)

- OCR for scanned PDFs (detected and warned, not read).
- Whisper fallback for videos without captions.
- Query rewriting for follow-up questions (Phase 3, with chat).
- Faithfulness measurement at scale; a larger, independently written golden set.
- `llama3.1` 8B was not evaluated: it does not fit the 4 GB GPU and would take about a minute per answer.
- Table rows that continue onto the next page lose their header row (known limitation, seen in Unit 1's application table).
- Paragraphs that start with a bold label ("Healthcare and Medical Imaging: ...") are not treated as sections, so lists of them get packed into one chunk (see 6.1, cv-08).

## 12. Next session: Phase 2, API + dashboard

1. REST API: collections, document upload (type/size checks), YouTube add, list/delete, job status over SSE.
2. Background ingest worker with status `pending > extracting > chunking > embedding > ready | failed`.
3. Local accounts (argon2 + HTTP-only cookies) and per-user data isolation.
4. A simple dashboard page for upload and a chat box (streaming answers with citations). The final stream event must carry the **cleaned** answer, and the UI must replace the streamed text with it. Uncited, content-free and nonexistent-citation answers get a visible flag, and every answer lists the retrieved sources so it can be checked.
5. Address latency (see 6.4).

## 13. Quick reference

```powershell
cd studybot\backend
$py = "$env:LOCALAPPDATA\StudyBot\venv\Scripts\python.exe"
& $py -m app.cli list
& $py -m app.cli ask "What is the difference between Sobel and Laplacian?" -c computer-vision
& $py -m app.cli ask "How do you log a parameter in MLflow?" -c mlops
& $py -m eval.run_retrieval --min-tokens 80 --rerank --show-misses
& $py -m eval.run_llm --models gemma2:2b        # ~20 minutes; results in %LOCALAPPDATA%\StudyBot\eval\results
```
