from pathlib import Path

from scripts.build_pydantic_benchmark_corpus import build_indices, run_pipeline
from scripts.run_pydantic_benchmark import aggregate, build_resolvers, load_gold, write_csv
from src.retrieval.evaluation import evaluate_queries
from src.retrieval.reranker import rerank
from src.retrieval.retrieval import CANDIDATE_K, retrieve_hybrid

"""
Stage 8B1: controlled ranking ablation over the frozen 42-query
change_retrieval core of Gold Set v1. Four modes, all built from the
same fixed candidate_k=40 pool per Stage 8B0's protocol -- nothing here
touches Gold Set v1, MiniLM, chunking, the corpus, or version-filter
semantics; those all stay exactly as run_pydantic_benchmark.py leaves
them (this script imports its helpers rather than reimplementing them,
so there's no risk of silently drifting from that convention).

- rrf_1_1: the existing, equal-weight RRF fusion -- identical to
  run_pydantic_benchmark.py's "hybrid" mode, reproduced here as this
  ablation's own baseline row for side-by-side comparison (not a second
  frozen baseline -- run_pydantic_benchmark.py's own CSVs remain the
  canonical Gold Set v1 baseline).
- rrf_dense2_sparse1 / rrf_dense1_sparse2: the same fusion, weighted
  2:1 and 1:2 (dense:sparse) via retrieve_hybrid's weights= param
  (Stage 8B1 addition to hybrid.py/retrieval.py -- weights=None
  elsewhere in the codebase is untouched and byte-identical).
- hybrid_reranked: takes the *unweighted* RRF 1:1 candidate_k=40 pool in
  full (output_k=CANDIDATE_K, not yet sliced to OUTPUT_K) and reorders
  it with Qwen/Qwen3-Reranker-0.6B (src/retrieval/reranker.py), then
  slices to OUTPUT_K -- "post-fusion reranking": scored on top of the
  standard fusion's own candidate pool, not a differently-pooled
  candidate set of its own.

Reports the same change-level Recall@K/MRR/nDCG aggregate as the frozen
benchmark, plus a focused per-mode rank trace for q_nl_02 and q_nl_03 --
the two known Stage 8A/8A.2 failures this ablation exists to investigate
(q_nl_02: fails under every mode, Dense rank 20/50 -- a ranking problem;
q_nl_03: Dense finds it top-5, RRF fusion buries it at 11/40 -- a fusion
dilution problem). Different failure mechanisms, so no single mode here
is expected to fix both.
"""

OUTPUT_DIR = Path("data/benchmark")
OUTPUT_K = 10
MODES = ["rrf_1_1", "rrf_dense2_sparse1", "rrf_dense1_sparse2", "hybrid_reranked"]
FOCUS_QUERY_IDS = ["q_nl_02", "q_nl_03"]


def make_run_query(mode: str, collection, sparse_index, chunks_by_id):
    def run(query_text: str) -> list[str]:
        if mode == "rrf_1_1":
            results = retrieve_hybrid(
                collection, sparse_index, query_text, chunks_by_id,
                output_k=OUTPUT_K, candidate_k=CANDIDATE_K,
            )
        elif mode == "rrf_dense2_sparse1":
            results = retrieve_hybrid(
                collection, sparse_index, query_text, chunks_by_id,
                output_k=OUTPUT_K, candidate_k=CANDIDATE_K, weights=(2.0, 1.0),
            )
        elif mode == "rrf_dense1_sparse2":
            results = retrieve_hybrid(
                collection, sparse_index, query_text, chunks_by_id,
                output_k=OUTPUT_K, candidate_k=CANDIDATE_K, weights=(1.0, 2.0),
            )
        elif mode == "hybrid_reranked":
            pool = retrieve_hybrid(
                collection, sparse_index, query_text, chunks_by_id,
                output_k=CANDIDATE_K, candidate_k=CANDIDATE_K,
            )
            results = rerank(query_text, pool, output_k=OUTPUT_K)
        else:
            raise ValueError(mode)

        return [r.chunk.chunk_id for r in results]

    return run


def rank_of_any_required(
    retrieved_chunk_ids: list[str], required_change_ids: list[str], chunk_to_change_ids: dict[str, list[str]]
) -> int | None:
    required = set(required_change_ids)
    for rank, chunk_id in enumerate(retrieved_chunk_ids, start=1):
        if required & set(chunk_to_change_ids.get(chunk_id, [])):
            return rank
    return None


def main() -> None:
    all_gold, metadata = load_gold()
    gold = [q for q in all_gold if q.evaluation_scope == "change_retrieval"]
    print(
        f"{metadata['name']} (review_revision={metadata['review_revision']}, "
        f"status={metadata['status']}) -- ranking ablation over {len(gold)} change_retrieval queries\n"
    )

    chunks, conn, _stats = run_pipeline()
    collection, sparse_index = build_indices(chunks)
    chunks_by_id = {c.chunk_id: c for c in chunks}
    chunk_to_change_ids, _chunk_to_evidence_ids = build_resolvers(chunks, conn)

    change_results = {}
    run_queries = {}
    for mode in MODES:
        run_query = make_run_query(mode, collection, sparse_index, chunks_by_id)
        run_queries[mode] = run_query
        change_results[mode] = evaluate_queries(
            gold, run_query, chunk_to_change_ids, required_ids_attr="required_change_ids"
        )

    print("=== Aggregate (change-level, 42-query change_retrieval core) ===")
    aggregate_rows = []
    for mode in MODES:
        agg = aggregate(change_results[mode])
        print(
            f"{mode:20s} R@5={agg['recall_at_5']:.3f} R@10={agg['recall_at_10']:.3f} "
            f"MRR={agg['mrr']:.3f} nDCG@5={agg['ndcg_at_5']:.3f} nDCG@10={agg['ndcg_at_10']:.3f}"
        )
        row = {"retrieval_mode": mode, "scored_against": "required_change_ids"}
        row.update(agg)
        aggregate_rows.append(row)

    write_csv(
        OUTPUT_DIR / "ranking_ablation_aggregate_results.csv",
        aggregate_rows,
        ["retrieval_mode", "scored_against", "recall_at_5", "recall_at_10", "mrr", "ndcg_at_5", "ndcg_at_10"],
    )

    detail_rows = []
    for mode in MODES:
        for r in change_results[mode]:
            detail_rows.append(
                {
                    "retrieval_mode": mode,
                    "query_id": r.query_id,
                    "recall_at_5": r.recall_at_5,
                    "recall_at_10": r.recall_at_10,
                    "mrr": r.mrr,
                }
            )
    write_csv(
        OUTPUT_DIR / "ranking_ablation_per_query_results.csv",
        detail_rows,
        ["retrieval_mode", "query_id", "recall_at_5", "recall_at_10", "mrr"],
    )

    by_id = {q.query_id: q for q in gold}
    print(f"\n=== Focus: {', '.join(FOCUS_QUERY_IDS)} (rank of first hit on required_change_ids, per mode) ===")
    for query_id in FOCUS_QUERY_IDS:
        if query_id not in by_id:
            print(f"  {query_id}: not in change_retrieval core, skipped")
            continue
        q = by_id[query_id]
        print(f"\n  {query_id} -- {q.query_text}")
        for mode in MODES:
            retrieved_ids = run_queries[mode](q.query_text)
            rank = rank_of_any_required(retrieved_ids, q.required_change_ids, chunk_to_change_ids)
            r = next(r for r in change_results[mode] if r.query_id == query_id)
            rank_str = str(rank) if rank else f"NOT FOUND in top {OUTPUT_K}"
            print(f"    {mode:20s} rank={rank_str:<20s} R@5={r.recall_at_5:.3f} R@10={r.recall_at_10:.3f}")

    print(f"\nCSV written to {OUTPUT_DIR}/ranking_ablation_*.csv")


if __name__ == "__main__":
    main()
