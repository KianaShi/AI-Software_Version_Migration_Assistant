import csv
import json
import sqlite3
from pathlib import Path

from scripts.build_pydantic_benchmark_corpus import build_indices, run_pipeline
from src.retrieval.dense_index import query_dense
from src.retrieval.hybrid import reciprocal_rank_fusion
from src.retrieval.retrieval import _FETCH_MULTIPLIER, retrieve_dense, retrieve_sparse
from src.retrieval.sparse_index import query_sparse

"""
Stage 8A diagnostic. Reads data/benchmark/per_query_results.csv (written
by the real benchmark run, top_k=10) as the AUTHORITATIVE list of which
queries fail -- do not recompute "which queries fail" independently.

Important pool-size fix: retrieve_hybrid()'s RRF candidate pool
(fetch_k = top_k * 4) scales with whatever top_k the caller passes, so a
naive "call retrieve_hybrid(top_k=50) to see deeper ranks" changes the
fusion pool itself and can show a DIFFERENT ranking than what the real
benchmark (top_k=10 -> fetch_k=40) actually produced -- caught this
empirically: q_multi_02 showed hybrid rank 6 under a top_k=50 pool but
recall@5=1.0 (rank <=5) under the real top_k=10 pool. Dense and sparse
ranks are pool-size-independent (no fusion, so requesting more results
doesn't reorder the ones already returned) and are safe to inspect at any
depth. Hybrid is reconstructed here at the EXACT fetch_k the real
benchmark used (top_k=10 -> fetch_k=40), unfused-and-untruncated, so the
reported rank is the real one, not an artifact of a bigger diagnostic pool.
"""

GOLD_PATH = Path("data/gold/pydantic_gold_queries.json")
RESULTS_CSV = Path("data/benchmark/per_query_results.csv")
BENCHMARK_TOP_K = 10  # must match scripts/run_pydantic_benchmark.py TOP_K
CUTOFFS = [5, 10, 20]  # capped at BENCHMARK_TOP_K * _FETCH_MULTIPLIER (40)


def rank_of_change(retrieved_chunk_ids: list[str], target_change_id: str, chunk_to_change_ids: dict) -> int | None:
    for rank, chunk_id in enumerate(retrieved_chunk_ids, start=1):
        if target_change_id in chunk_to_change_ids.get(chunk_id, []):
            return rank
    return None


def find_failing_query_ids() -> list[str]:
    """Authoritative: any non-negative query with hybrid recall_at_5 < 1.0 in the real benchmark run."""
    failing = []
    with RESULTS_CSV.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["retrieval_mode"] == "hybrid" and float(row["recall_at_5"]) < 1.0:
                failing.append(row["query_id"])
    return failing


def hybrid_rank_at_benchmark_pool_size(query_text, collection, sparse_index, chunks_by_id, target_change_id, chunk_to_change_ids) -> int | None:
    fetch_k = BENCHMARK_TOP_K * _FETCH_MULTIPLIER  # exactly what the real benchmark's retrieve_hybrid(top_k=10) uses internally
    dense_raw = query_dense(collection, query_text, chunks_by_id, fetch_k=fetch_k)
    sparse_raw = query_sparse(sparse_index, query_text, chunks_by_id, fetch_k=fetch_k)
    fused = reciprocal_rank_fusion(
        [[r.chunk.chunk_id for r in dense_raw], [r.chunk.chunk_id for r in sparse_raw]]
    )
    fused_ids = [chunk_id for chunk_id, _score in fused]
    return rank_of_change(fused_ids, target_change_id, chunk_to_change_ids)


def main() -> None:
    gold_records = json.loads(GOLD_PATH.read_text(encoding="utf-8"))
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
    print(f"Non-negative queries with hybrid Recall@5 < 1.0 (from {RESULTS_CSV}): {failing_query_ids}\n")

    for query_id in failing_query_ids:
        q = gold[query_id]
        print(f"=== {query_id} | {q['query_text']} ===")
        print(f"taxonomy: {q['query_type']}")

        dense_full = retrieve_dense(collection, q["query_text"], chunks_by_id, top_k=50)
        sparse_full = retrieve_sparse(sparse_index, q["query_text"], chunks_by_id, top_k=50)
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
                ("hybrid", hybrid_rank, f"(pool: top {BENCHMARK_TOP_K * _FETCH_MULTIPLIER}, matches real benchmark)"),
            ):
                rank_str = str(rank) if rank else "NOT FOUND"
                hits = " ".join(("YES".ljust(7) if rank and rank <= c else "no".ljust(7)) for c in CUTOFFS)
                print(f"  {mode_name:10s} {rank_str:<20s} {hits}  {note}")
        print()


if __name__ == "__main__":
    main()
