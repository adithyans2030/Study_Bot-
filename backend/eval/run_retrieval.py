"""Retrieval evaluation: hit@k and MRR for dense / BM25 / hybrid (+ reranker), an optional
chunk-size sweep, and calibration of the 'not in your materials' score gate.

    python -m eval.run_retrieval [--corpus-dir DIR] [--min-tokens 0,80,150] [--rerank]

No LLM is involved, so this is fast and deterministic.
"""
import argparse
import statistics
import sys

from eval.common import build_bot, default_corpus_dir, ingest_corpus, is_relevant, load_golden

MODES = [("dense", "dense", False), ("bm25", "bm25", False), ("hybrid", "hybrid", False)]


def group_of(item_id: str) -> str:
    if item_id.startswith("yt"):
        return "video"
    number = int(item_id.split("-")[1]) if item_id.startswith("cv") else 0
    return "notes-casual" if 54 <= number <= 58 else "notes-formal"


def summarize(ranks: list[int | None]) -> dict:
    n = len(ranks)
    return {"n": n, **{f"hit@{k}": sum(bool(r and r <= k) for r in ranks) / n for k in (1, 3, 5)},
            "mrr": statistics.mean(1 / r if r else 0.0 for r in ranks)}


def evaluate(bot, golden, mode, rerank, k_max=10):
    """Returns (overall metrics, per-group metrics, [(id, question, rank)] for rank != 1)."""
    ranks: list[int | None] = []
    by_group: dict[str, list[int | None]] = {}
    misses = []
    for item in golden:
        if not item["answerable"]:
            continue
        result = bot.search(item["q"], [item["collection"]], k=k_max, mode=mode, rerank=rerank)
        rank = next((i for i, h in enumerate(result.hits, 1) if is_relevant(h.chunk, item["expect"])), None)
        ranks.append(rank)
        by_group.setdefault(group_of(item["id"]), []).append(rank)
        if rank != 1:
            misses.append((item["id"], item["q"], rank))
    return summarize(ranks), {g: summarize(r) for g, r in by_group.items()}, misses


def gate_calibration(bot, golden):
    """Best-match cosine for answerable vs unanswerable questions, and what each threshold would do."""
    scores = {True: [], False: []}
    for item in golden:
        result = bot.search(item["q"], [item["collection"]], k=1, mode="dense")
        scores[item["answerable"]].append((result.best_dense, item["id"]))
    yes = sorted(s for s, _ in scores[True])
    no = sorted(s for s, _ in scores[False])
    print(f"\n  best-match cosine  answerable:   min {yes[0]:.3f}  p5 {yes[int(len(yes)*0.05)]:.3f}  "
          f"median {statistics.median(yes):.3f}  max {yes[-1]:.3f}")
    print(f"  best-match cosine  unanswerable: min {no[0]:.3f}  median {statistics.median(no):.3f}  max {no[-1]:.3f}")
    print("  gate threshold -> falsely refused answerable | correctly refused unanswerable")
    for t in (0.50, 0.55, 0.60, 0.65, 0.70, 0.75):
        fr = sum(s < t for s in yes) / len(yes)
        ok = sum(s < t for s in no) / len(no)
        print(f"    {t:.2f}          -> {fr:6.1%}                     | {ok:6.1%}")
    return yes, no


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--corpus-dir", type=lambda p: __import__("pathlib").Path(p), default=default_corpus_dir())
    parser.add_argument("--min-tokens", default="80", help="comma-separated chunk_min_tokens values to sweep")
    parser.add_argument("--target-tokens", default="320", help="comma-separated chunk_target_tokens values to sweep")
    parser.add_argument("--rerank", action="store_true", help="also evaluate hybrid + cross-encoder reranker")
    parser.add_argument("--show-misses", action="store_true")
    parser.add_argument("--reingest", action="store_true", help="re-index even if the files are unchanged")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    golden = load_golden()
    answerable = sum(g["answerable"] for g in golden)
    print(f"{len(golden)} questions ({answerable} answerable, {len(golden) - answerable} not in the materials)")

    mins = [int(x) for x in args.min_tokens.split(",")]
    targets = [int(x) for x in args.target_tokens.split(",")]
    configs = [(m, t) for t in targets for m in mins]
    for min_tokens, target in configs:
        print(f"\n=== chunk_min_tokens={min_tokens} chunk_target_tokens={target} ===")
        db_name = f"eval_min{min_tokens}.db" if target == 320 else f"eval_min{min_tokens}_t{target}.db"
        bot = build_bot(db_name, chunk_min_tokens=min_tokens, chunk_target_tokens=target,
                        chunk_max_tokens=int(target * 1.3), use_reranker=args.rerank)
        ingest_corpus(bot, args.corpus_dir, force=args.reingest, log=lambda _: None)
        chunk_total = sum(c["chunks"] for c in bot.store.list_collections())
        print(f"  total chunks: {chunk_total}")

        rows = list(MODES) + ([("hybrid+rerank", "hybrid", True)] if args.rerank else [])
        print(f"  {'mode':14} {'hit@1':>7} {'hit@3':>7} {'hit@5':>7} {'MRR':>7}   (per group: hit@1 / hit@5)")
        missed_top5 = {}
        for name, mode, rerank in rows:
            metrics, groups, misses = evaluate(bot, golden, mode, rerank)
            per_group = "  ".join(f"{g} {m['hit@1']:.0%}/{m['hit@5']:.0%}(n={m['n']})" for g, m in sorted(groups.items()))
            print(f"  {name:14} {metrics['hit@1']:7.1%} {metrics['hit@3']:7.1%} {metrics['hit@5']:7.1%} {metrics['mrr']:7.3f}   {per_group}")
            missed_top5[name] = [m for m in misses if m[2] is None or m[2] > 5]
        if args.show_misses:
            for name, missed in missed_top5.items():
                if missed:
                    print(f"  {name}: questions whose best chunk is NOT in the top 5:")
                    for qid, q, rank in missed:
                        print(f"    {qid} rank={rank}: {q}")
        if (min_tokens, target) == configs[0]:
            gate_calibration(bot, golden)
    return 0


if __name__ == "__main__":
    sys.exit(main())
