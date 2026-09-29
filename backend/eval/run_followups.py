"""Which follow-up strategy finds the right passages? Retrieval only (plus rewrite timing for `llm`).

    python -m eval.run_followups [--modes off,concat,llm] [--model gemma2:2b]

Each case is a two-turn conversation. The "previous answer" given to the rewriter is the best
passage found for the first question, standing in for a real answer.
"""
import argparse
import asyncio
import json
import statistics
import sys
import time
from pathlib import Path

from app.rag.followup import looks_like_follow_up, search_query
from eval.common import HERE, build_bot, default_corpus_dir, ingest_corpus, is_relevant

CASES = HERE / "followups.jsonl"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--modes", default="off,concat,llm")
    parser.add_argument("--model", default="gemma2:2b")
    parser.add_argument("--k", type=int, default=4)
    parser.add_argument("--corpus-dir", type=Path, default=default_corpus_dir())
    parser.add_argument("--show", action="store_true", help="print each search query")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    bot = build_bot("eval_min80.db")
    ingest_corpus(bot, args.corpus_dir, log=lambda _: None)
    cases = [json.loads(line) for line in CASES.read_text(encoding="utf-8").splitlines() if line.strip()]

    print(f"{len(cases)} cases ({sum(c['kind'] == 'followup' for c in cases)} follow-ups, "
          f"{sum(c['kind'] == 'independent' for c in cases)} independent); hit@{args.k}, MRR@10\n")
    prepared = []
    for case in cases:
        first_hits = bot.search(case["first"], [case["collection"]], k=1).hits
        answer = first_hits[0].chunk.text if first_hits else ""
        prepared.append((case, [(case["first"], answer)]))
    detected = {c["id"]: looks_like_follow_up(c["second"]) for c in cases}
    print("detector: flags", sum(detected[c['id']] for c in cases if c['kind'] == 'followup'), "of",
          sum(c['kind'] == 'followup' for c in cases), "follow-ups;",
          sum(detected[c['id']] for c in cases if c['kind'] == 'independent'), "of",
          sum(c['kind'] == 'independent' for c in cases), "independent questions (should be low)\n")

    for mode in args.modes.split(","):
        stats = {"followup": [], "independent": []}
        seconds = []
        for case, history in prepared:
            started = time.perf_counter()
            query = asyncio.run(search_query(mode, case["second"], history, base_url=bot.settings.ollama_url,
                                             model=args.model, num_ctx=bot.settings.num_ctx))
            seconds.append(time.perf_counter() - started)
            hits = bot.search(query, [case["collection"]], k=10).hits
            rank = next((i for i, h in enumerate(hits, 1) if is_relevant(h.chunk, case["expect"])), None)
            stats[case["kind"]].append(rank)
            if args.show and query != case["second"]:
                print(f"    [{mode}] {case['id']}: {case['second']!r} -> {query!r}  (rank {rank})")
        for kind, ranks in stats.items():
            hit = sum(bool(r and r <= args.k) for r in ranks) / len(ranks)
            mrr = statistics.mean(1 / r if r else 0 for r in ranks)
            print(f"  {mode:7} {kind:12} hit@{args.k} {hit:6.1%}  MRR {mrr:.3f}  (n={len(ranks)})")
        print(f"  {mode:7} extra time per question: {statistics.mean(seconds):.2f}s\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
