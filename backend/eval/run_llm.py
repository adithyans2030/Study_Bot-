"""LLM evaluation over the golden set, one or more Ollama models.

    python -m eval.run_llm --models gemma2:2b [--stride 1] [--only all|answerable|unanswerable]
    python -m eval.run_llm --models gemma2:2b --resume PATH_TO_PARTIAL.jsonl

For every question it retrieves (hybrid, top-k), asks the model, and records:
  answerable   -> false refusals, keyword correctness (a cheap proxy, NOT faithfulness),
                  valid citations, whether the right passage was even in the context
  unanswerable -> how often the raw model refuses (the score gate is bypassed on purpose)
  latency      -> prompt tokens, time to first token, generation speed

Every answer is appended to a .jsonl file the moment it is produced, so a crash loses at most one
question and `--resume` continues where it stopped. Transient Ollama errors are retried.
"""
import argparse
import asyncio
import json
import statistics
import sys
import time
from pathlib import Path

from app.core.ollama import OllamaError, chat_stream
from app.rag.prompt import is_empty_answer
from eval.common import build_bot, default_corpus_dir, ingest_corpus, is_relevant, keywords_ok, load_golden

RETRIES = 3
RETRY_WAIT_SECONDS = 15


def pick(golden, only: str, stride: int):
    answerable = [g for g in golden if g["answerable"]][::stride]
    unanswerable = [g for g in golden if not g["answerable"]]
    if only == "answerable":
        return answerable
    if only == "unanswerable":
        return unanswerable
    return sorted(answerable + unanswerable, key=lambda g: golden.index(g))


async def warm_up(bot, model):
    """Load the model with the real context size so the first timed question isn't a cold start."""
    async for _ in chat_stream(bot.settings.ollama_url, model, [{"role": "user", "content": "Reply with OK."}],
                               num_ctx=bot.settings.num_ctx, num_predict=4):
        pass


async def ask_with_retry(bot, item, model):
    for attempt in range(1, RETRIES + 1):
        try:
            return await bot.ask(item["q"], [item["collection"]], model=model, use_gate=False)
        except OllamaError as exc:
            print(f"    ollama error on {item['id']} (attempt {attempt}/{RETRIES}): {exc}", flush=True)
            if attempt == RETRIES:
                return None
            await asyncio.sleep(RETRY_WAIT_SECONDS)


def load_done(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


async def run_model(bot, model, items, sink: Path, done: list[dict]):
    finished = {r["id"] for r in done}
    todo = [item for item in items if item["id"] not in finished]
    print(f"  {len(done)} already recorded, {len(todo)} to run", flush=True)
    records = list(done)
    if not todo:
        return records
    await warm_up(bot, model)
    failed = []
    for n, item in enumerate(todo, 1):
        answer = await ask_with_retry(bot, item, model)
        if answer is None:
            failed.append(item["id"])
            continue
        in_context = any(is_relevant(h.chunk, item["expect"]) for h in answer.hits) if item["answerable"] else None
        record = {
            "id": item["id"], "q": item["q"], "answerable": item["answerable"], "answer": answer.text,
            "refused": answer.refused, "cited": answer.cited, "invalid_citations": answer.invalid_citations,
            "in_context": in_context, "best_dense": round(answer.best_dense, 3),
            "kw_ok": keywords_ok(answer.text, item["kw"]) if item["answerable"] and not answer.refused else None,
            "prompt_tokens": answer.prompt_tokens, "prompt_seconds": answer.prompt_seconds,
            "ttft": answer.first_token_seconds, "total": answer.total_seconds,
            "tokens": answer.tokens, "tps": answer.tokens_per_second,
        }
        records.append(record)
        with open(sink, "a", encoding="utf-8") as handle:  # saved immediately: a crash loses nothing
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        flag = "REFUSED" if answer.refused else "answered"
        print(f"  [{n:2}/{len(todo)}] {item['id']:6} {flag:8} ttft={answer.first_token_seconds:5.1f}s "
              f"total={answer.total_seconds:5.1f}s  {item['q'][:55]}", flush=True)
    if failed:
        print(f"\n  WARNING: {len(failed)} question(s) failed after {RETRIES} attempts and are NOT in the "
              f"results: {failed}. Re-run with --resume {sink}", flush=True)
    return records


def pct(x: int, n: int) -> str:
    return f"{x}/{n} ({x / n:.0%})" if n else "n/a"


def median(values):
    values = [v for v in values if v]
    return statistics.median(values) if values else 0.0


def summarize(model, records):
    ans = [r for r in records if r["answerable"]]
    un = [r for r in records if not r["answerable"]]
    answered = [r for r in ans if not r["refused"]]
    print(f"\n=== {model} ===")
    if ans:
        print(f"  answerable questions:        {len(ans)}")
        print(f"    right passage in context:  {pct(sum(bool(r['in_context']) for r in ans), len(ans))}")
        print(f"    falsely refused:           {pct(sum(r['refused'] for r in ans), len(ans))}")
        print(f"    keyword check passed:      {pct(sum(bool(r['kw_ok']) for r in answered), len(answered))}  (of answered; proxy for correctness)")
        print(f"    has a valid citation:      {pct(sum(bool(r['cited']) for r in answered), len(answered))}  (of answered)")
        print(f"    content-free (citations only): {pct(sum(is_empty_answer(r['answer']) for r in answered), len(answered))}  (of answered)")
        print(f"    invalid citations dropped: {sum(r['invalid_citations'] for r in answered)}")
    if un:
        print(f"  unanswerable questions:      {len(un)}")
        print(f"    correctly refused:         {pct(sum(r['refused'] for r in un), len(un))}")
        for r in un:
            if not r["refused"]:
                print(f"      answered anyway: {r['id']} {r['q'][:60]}  -> {r['answer'][:90]!r}")
    timed = records[1:] if len(records) > 1 else records
    print(f"  latency (median): prompt {median(r['prompt_tokens'] for r in timed):.0f} tokens, "
          f"prompt speed {median(r['prompt_tokens'] / r['prompt_seconds'] for r in timed if r['prompt_seconds']):.0f} tok/s, "
          f"first token {median(r['ttft'] for r in timed):.1f}s, total {median(r['total'] for r in timed):.1f}s, "
          f"generation {median(r['tps'] for r in timed):.0f} tok/s")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--models", default="gemma2:2b")
    parser.add_argument("--only", choices=["all", "answerable", "unanswerable"], default="all")
    parser.add_argument("--stride", type=int, default=1, help="use every Nth answerable question (faster for big models)")
    parser.add_argument("--corpus-dir", type=Path, default=default_corpus_dir())
    parser.add_argument("--reingest", action="store_true", help="re-index even if the files are unchanged")
    parser.add_argument("--resume", type=Path, help="continue a partial .jsonl (single model only)")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    models = args.models.split(",")
    if args.resume and len(models) != 1:
        parser.error("--resume works with exactly one model")

    bot = build_bot("eval_min80.db")
    ingest_corpus(bot, args.corpus_dir, log=lambda _: None, force=args.reingest)
    items = pick(load_golden(), args.only, args.stride)
    out_dir = bot.settings.home / "eval" / "results"
    out_dir.mkdir(parents=True, exist_ok=True)

    exit_code = 0
    for model in models:
        sink = args.resume or out_dir / f"llm_{model.replace(':', '_')}_{time.strftime('%Y%m%d_%H%M%S')}.jsonl"
        print(f"\nRunning {len(items)} questions on {model} -> {sink}", flush=True)
        try:
            records = asyncio.run(run_model(bot, model, items, sink, load_done(sink)))
        except OllamaError as exc:
            print(f"\nERROR: could not run {model}: {exc}", flush=True)
            exit_code = 1
            continue
        wanted = {item["id"] for item in items}
        records = [r for r in records if r["id"] in wanted]
        summarize(model, records)
        if len(records) < len(items):
            exit_code = 1
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
