import json
import sqlite3
from pathlib import Path

from scripts.build_pydantic_benchmark_corpus import build_indices, run_pipeline
from src.retrieval.retrieval import retrieve_dense, retrieve_hybrid, retrieve_sparse

"""
Stage 8A diagnostic: for a given set of failing query_ids, find the rank
at which each required change's supporting evidence/chunk actually
appears under Dense / BM25 / Hybrid, at cutoffs 5/10/20/50. This is what
separates a RANKING problem (right chunk is indexed, just scores too low
for top-5) from a SEMANTIC_MISMATCH/CORPUS_GAP/EXTRACTION_GAP (the right
chunk never surfaces at all, or never existed to begin with).
"""

GOLD_PATH = Path("data/gold/pydantic_gold_queries.json")
CUTOFFS = [5, 10, 20, 50]
FETCH_K = 50


def rank_of_change(retrieved_chunk_ids: list[str], target_change_ids: set[str], chunk_to_change_ids: dict) -> int | None:
    for rank, chunk_id in enumerate(retrieved_chunk_ids, start=1):
        if set(chunk_to_change_ids.get(chunk_id, [])) & target_change_ids:
            return rank
    return None


def main(query_ids: list[str]) -> None:
    gold = {q["query_id"]: q for q in json.loads(GOLD_PATH.read_text(encoding="utf-8"))}
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

    changes = {r["change_id"]: dict(r) for r in conn.execute("SELECT * FROM change_records")}

    for query_id in query_ids:
        q = gold[query_id]
        target_change_ids = set(q["required_change_ids"])
        print(f"\n=== {query_id} | {q['query_text']} ===")
        print("gold required changes:")
        for cid in q["required_change_ids"]:
            c = changes[cid]
            repl = f" -> {c['replacement_symbol']}" if c["replacement_symbol"] else ""
            print(f"  {cid}  {c['symbol_name']} ({c['change_type']}){repl}")

        modes = {
            "dense": lambda: retrieve_dense(collection, q["query_text"], chunks_by_id, top_k=FETCH_K),
            "sparse": lambda: retrieve_sparse(sparse_index, q["query_text"], chunks_by_id, top_k=FETCH_K),
            "hybrid": lambda: retrieve_hybrid(collection, sparse_index, q["query_text"], chunks_by_id, top_k=FETCH_K),
        }

        print(f"\n{'mode':10s} {'rank':6s} " + " ".join(f"top{c:<4d}" for c in CUTOFFS))
        for mode_name, run in modes.items():
            results = run()
            retrieved_ids = [r.chunk.chunk_id for r in results]
            rank = rank_of_change(retrieved_ids, target_change_ids, chunk_to_change_ids)
            rank_str = str(rank) if rank else "NOT FOUND in top 50"
            hits = " ".join(
                ("YES".ljust(7) if rank and rank <= c else "no".ljust(7)) for c in CUTOFFS
            )
            print(f"{mode_name:10s} {rank_str:6s} {hits}")


if __name__ == "__main__":
    main(["q_nl_02", "q_amb_01"])
