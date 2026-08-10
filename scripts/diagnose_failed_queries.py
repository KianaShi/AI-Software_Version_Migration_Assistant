import csv
import json
import sqlite3
from pathlib import Path

from scripts.build_pydantic_benchmark_corpus import build_indices, run_pipeline
from src.retrieval.retrieval import CANDIDATE_K, retrieve_dense, retrieve_hybrid, retrieve_sparse

"""
Stage 8A diagnostic. Reads data/benchmark/per_query_results.csv (written
by the real benchmark run) as the AUTHORITATIVE list of which queries
fail -- do not recompute "which queries fail" independently.

Stage 8B0 note: this script originally had to manually reconstruct
Hybrid's fused ranking at the exact fetch_k the real benchmark used,
because retrieve_hybrid()'s RRF candidate pool used to scale with
whatever output top_k the caller passed (fetch_k = top_k * 4) -- a naive
"call retrieve_hybrid(top_k=50) to see deeper ranks" changed the fusion
pool itself and could show a DIFFERENT ranking than the real benchmark
produced (caught empirically: q_multi_02 showed hybrid rank 6 under a
top_k=50 pool but recall@5=1.0 under the real top_k=10 pool). Now that
retrieval.py fixes candidate_k independently of output_k (see its module
docstring), this script just calls retrieve_hybrid() directly with
output_k=candidate_k=CANDIDATE_K to see the whole real candidate pool,
unfused-reconstruction no longer needed -- the public API *is* the real
ranking now, at any output_k up to CANDIDATE_K, since it fixes the same
candidate pool without a separate depth-specific hack.
"""

GOLD_PATH = Path("data/gold/pydantic_gold_queries.json")
RESULTS_CSV = Path("data/benchmark/per_query_results.csv")
CUTOFFS = [5, 10, 20]  # capped at CANDIDATE_K (40)


def rank_of_change(retrieved_chunk_ids: list[str], target_change_id: str, chunk_to_change_ids: dict) -> int | None:
    for rank, chunk_id in enumerate(retrieved_chunk_ids, start=1):
        if target_change_id in chunk_to_change_ids.get(chunk_id, []):
            return rank
    return None


def find_failing_query_ids() -> list[str]:
    """
    Authoritative: any change_retrieval-scope query with hybrid recall_at_5
    < 1.0 in the real benchmark run. per_query_results.csv is built only
    from evaluation_scope=="change_retrieval" queries (see
    run_pydantic_benchmark.py), so stability/query_planner queries never
    appear here to begin with.
    """
    failing = []
    with RESULTS_CSV.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["retrieval_mode"] == "hybrid" and float(row["recall_at_5"]) < 1.0:
                failing.append(row["query_id"])
    return failing


def hybrid_rank_at_benchmark_pool_size(query_text, collection, sparse_index, chunks_by_id, target_change_id, chunk_to_change_ids) -> int | None:
    # output_k=CANDIDATE_K surfaces the whole real candidate pool -- the
    # same pool the real benchmark's retrieve_hybrid(output_k=10) fuses
    # over internally, since candidate_k no longer depends on output_k.
    results = retrieve_hybrid(collection, sparse_index, query_text, chunks_by_id, output_k=CANDIDATE_K)
    fused_ids = [r.chunk.chunk_id for r in results]
    return rank_of_change(fused_ids, target_change_id, chunk_to_change_ids)


def main() -> None:
    gold_records = json.loads(GOLD_PATH.read_text(encoding="utf-8"))["queries"]
    gold = {r["query_id"]: r for r in gold_records}
    chunks, conn, _ = run_pipeline()
    collection, sparse_index = build_indices(chunks)
    chunks_by_id = {c.chunk_id: c for c in chunks}

    chunk_to_change_ids: dict[str, list[str]] = {}
    for chunk in chunks:
        if chunk.evidence_id is None:
            continue
        rows = conn.execute(
            "SELECT change_id FROM evidence_links WHERE evidence_id = ?", (chunk.evidence_id,)
        ).fetchall()
        chunk_to_change_ids[chunk.chunk_id] = [row[0] for row in rows]

    conn.row_factory = sqlite3.Row
    changes = {r["change_id"]: dict(r) for r in conn.execute("SELECT * FROM change_records")}

    failing_query_ids = find_failing_query_ids()
    print(f"change_retrieval-scope queries with hybrid Recall@5 < 1.0 (from {RESULTS_CSV}): {failing_query_ids}\n")

    for query_id in failing_query_ids:
        q = gold[query_id]
        print(f"=== {query_id} | {q['query_text']} ===")
        print(f"taxonomy: {q['query_type']}")

        dense_full = retrieve_dense(collection, q["query_text"], chunks_by_id, output_k=50, candidate_k=50)
        sparse_full = retrieve_sparse(sparse_index, q["query_text"], chunks_by_id, output_k=50, candidate_k=50)
        dense_ids = [r.chunk.chunk_id for r in dense_full]
        sparse_ids = [r.chunk.chunk_id for r in sparse_full]

        for cid in q["required_change_ids"]:
            c = changes[cid]
            dense_rank = rank_of_change(dense_ids, cid, chunk_to_change_ids)
            sparse_rank = rank_of_change(sparse_ids, cid, chunk_to_change_ids)
            hybrid_rank = hybrid_rank_at_benchmark_pool_size(
                q["query_text"], collection, sparse_index, chunks_by_id, cid, chunk_to_change_ids
            )

            print(f"\n  -- {c['symbol_name']} ({cid}) --")
            print(f"  {'mode':10s} {'rank':20s} " + " ".join(f"top{c:<4d}" for c in CUTOFFS))
            for mode_name, rank, note in (
                ("dense", dense_rank, "(pool: top 50, stable)"),
                ("sparse", sparse_rank, "(pool: top 50, stable)"),
                ("hybrid", hybrid_rank, f"(pool: top {CANDIDATE_K}, matches real benchmark)"),
            ):
                rank_str = str(rank) if rank else "NOT FOUND"
                hits = " ".join(("YES".ljust(7) if rank and rank <= c else "no".ljust(7)) for c in CUTOFFS)
                print(f"  {mode_name:10s} {rank_str:<20s} {hits}  {note}")
        print()


if __name__ == "__main__":
    main()
