import csv
import json
import sqlite3
from pathlib import Path

from scripts.build_pydantic_benchmark_corpus import build_indices, run_pipeline
from src.retrieval.evaluation import GoldQuery, evaluate_queries
from src.retrieval.models import Chunk
from src.retrieval.retrieval import CANDIDATE_K, retrieve_dense, retrieve_hybrid, retrieve_sparse
from src.retrieval.version_filter import query_version_interval

"""
Stage 7 benchmark runner: Dense vs. Sparse (BM25) vs. Hybrid (RRF) vs.
Hybrid + version filter, over the pydantic 1.10.x -> 2.x gold set, scored
both at the change level (required_change_ids -> Migration Chain Recall
precursor) and the evidence level (relevant_evidence_ids -> plain
Recall@K/MRR/nDCG). All numbers below are produced by actually running
this script, not hand-written.

Stage 8B0: OUTPUT_K (how many results each retriever returns/is scored
on) and CANDIDATE_K (the fixed candidate pool retrieval.py fetches/fuses
over before slicing, imported from retrieval.py so this runner can never
drift from what retrieval.py actually uses) are now independent -- see
src/retrieval/retrieval.py's module docstring. OUTPUT_K stays 10, same
as the old TOP_K, and CANDIDATE_K's default (40) is exactly what the old
fetch_k = top_k * 4 already worked out to at top_k=10, so this run
reproduces the frozen Gold Set v1 baseline numbers rather than moving
them -- the fix changes what happens when output_k varies, not this
runner's fixed-at-10 behavior.
"""

GOLD_PATH = Path("data/gold/pydantic_gold_queries.json")
OUTPUT_DIR = Path("data/benchmark")
OUTPUT_K = 10
MODES = ["dense", "sparse", "hybrid", "hybrid_version_filtered"]


def load_gold() -> tuple[list[GoldQuery], dict]:
    data = json.loads(GOLD_PATH.read_text(encoding="utf-8"))
    metadata = data["metadata"]
    queries = [
        GoldQuery(
            query_id=r["query_id"],
            query_text=r["query_text"],
            query_type=r["query_type"],
            from_version=r.get("from_version"),
            to_version=r.get("to_version"),
            required_change_ids=r["required_change_ids"],
            relevant_evidence_ids=r["relevant_evidence_ids"],
            evaluation_scope=r.get("evaluation_scope", "change_retrieval"),
        )
        for r in data["queries"]
    ]
    return queries, metadata


def build_resolvers(
    chunks: list[Chunk], conn: sqlite3.Connection
) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    chunk_to_evidence_ids: dict[str, list[str]] = {}
    chunk_to_change_ids: dict[str, list[str]] = {}

    for chunk in chunks:
        if chunk.evidence_id is None:
            continue
        chunk_to_evidence_ids[chunk.chunk_id] = [chunk.evidence_id]
        rows = conn.execute(
            "SELECT change_id FROM evidence_links WHERE evidence_id = ?",
            (chunk.evidence_id,),
        ).fetchall()
        chunk_to_change_ids[chunk.chunk_id] = [row[0] for row in rows]

    return chunk_to_change_ids, chunk_to_evidence_ids


def make_run_query(mode: str, collection, sparse_index, chunks_by_id):
    def run(query_text: str) -> list[str]:
        version_filter = query_version_interval(query_text) if mode == "hybrid_version_filtered" else None

        if mode == "dense":
            results = retrieve_dense(collection, query_text, chunks_by_id, output_k=OUTPUT_K, candidate_k=CANDIDATE_K)
        elif mode == "sparse":
            results = retrieve_sparse(sparse_index, query_text, chunks_by_id, output_k=OUTPUT_K, candidate_k=CANDIDATE_K)
        elif mode == "hybrid":
            results = retrieve_hybrid(
                collection, sparse_index, query_text, chunks_by_id, output_k=OUTPUT_K, candidate_k=CANDIDATE_K
            )
        elif mode == "hybrid_version_filtered":
            results = retrieve_hybrid(
                collection, sparse_index, query_text, chunks_by_id,
                output_k=OUTPUT_K, candidate_k=CANDIDATE_K, version_filter=version_filter,
            )
        else:
            raise ValueError(mode)

        return [r.chunk.chunk_id for r in results]

    return run


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def aggregate(results) -> dict[str, float]:
    return {
        "recall_at_5": mean([r.recall_at_5 for r in results]),
        "recall_at_10": mean([r.recall_at_10 for r in results]),
        "mrr": mean([r.mrr for r in results]),
        "ndcg_at_5": mean([r.ndcg_at_5 for r in results]),
        "ndcg_at_10": mean([r.ndcg_at_10 for r in results]),
    }


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def failure_quadrant(gold: list[GoldQuery], change_results: dict[str, list]) -> dict[str, list[str]]:
    """
    dense-only-succeeds / sparse-only-succeeds / hybrid-fixes-both /
    all-fail, based on change-level Recall@5 (== 1.0 counts as success).
    `gold` here is already filtered to evaluation_scope == "change_retrieval"
    by the caller, so stability (negative) and query_planner queries never
    reach this function.
    """
    by_id = {q.query_id: q for q in gold}
    dense_r = {r.query_id: r.recall_at_5 for r in change_results["dense"]}
    sparse_r = {r.query_id: r.recall_at_5 for r in change_results["sparse"]}
    hybrid_r = {r.query_id: r.recall_at_5 for r in change_results["hybrid"]}

    quadrants: dict[str, list[str]] = {
        "dense_only_succeeds": [],
        "sparse_only_succeeds": [],
        "hybrid_fixes_both": [],
        "all_fail": [],
    }

    for query_id in by_id:
        d, s, h = dense_r[query_id] >= 0.999, sparse_r[query_id] >= 0.999, hybrid_r[query_id] >= 0.999

        if d and not s:
            quadrants["dense_only_succeeds"].append(query_id)
        if s and not d:
            quadrants["sparse_only_succeeds"].append(query_id)
        if h and not d and not s:
            quadrants["hybrid_fixes_both"].append(query_id)
        if not d and not s and not h:
            quadrants["all_fail"].append(query_id)

    return quadrants


def main() -> None:
    all_gold, metadata = load_gold()
    gold = [q for q in all_gold if q.evaluation_scope == "change_retrieval"]
    stability = [q for q in all_gold if q.evaluation_scope == "stability"]
    query_planner = [q for q in all_gold if q.evaluation_scope == "query_planner"]
    scoped_out = stability + query_planner
    print(f"{metadata['name']} (review_revision={metadata['review_revision']}, "
          f"status={metadata['status']}, scope={metadata['migration_scope']})\n")
    chunks, conn, _stats = run_pipeline()
    collection, sparse_index = build_indices(chunks)
    chunks_by_id = {c.chunk_id: c for c in chunks}
    chunk_to_change_ids, chunk_to_evidence_ids = build_resolvers(chunks, conn)

    change_results = {}
    evidence_results = {}
    scoped_out_results = {}

    for mode in MODES:
        run_query = make_run_query(mode, collection, sparse_index, chunks_by_id)
        change_results[mode] = evaluate_queries(
            gold, run_query, chunk_to_change_ids, required_ids_attr="required_change_ids"
        )
        evidence_results[mode] = evaluate_queries(
            gold, run_query, chunk_to_evidence_ids, required_ids_attr="relevant_evidence_ids"
        )
        if scoped_out:
            scoped_out_results[mode] = evaluate_queries(
                scoped_out, run_query, chunk_to_change_ids, required_ids_attr="required_change_ids"
            )

    # --- aggregate table (change-level, the primary migration-task metric) ---
    aggregate_rows = []
    for mode in MODES:
        row = {"retrieval_mode": mode, "scored_against": "required_change_ids"}
        row.update(aggregate(change_results[mode]))
        aggregate_rows.append(row)
    for mode in MODES:
        row = {"retrieval_mode": mode, "scored_against": "relevant_evidence_ids"}
        row.update(aggregate(evidence_results[mode]))
        aggregate_rows.append(row)

    fieldnames = ["retrieval_mode", "scored_against", "recall_at_5", "recall_at_10", "mrr", "ndcg_at_5", "ndcg_at_10"]
    write_csv(OUTPUT_DIR / "aggregate_results.csv", aggregate_rows, fieldnames)

    # --- per-query-type slice (change-level) ---
    slice_rows = []
    query_types = sorted({q.query_type for q in gold})
    for mode in MODES:
        by_query_id = {r.query_id: r for r in change_results[mode]}
        for query_type in query_types:
            subset = [by_query_id[q.query_id] for q in gold if q.query_type == query_type]
            row = {"retrieval_mode": mode, "query_type": query_type, "n_queries": len(subset)}
            row.update(aggregate(subset))
            slice_rows.append(row)

    write_csv(
        OUTPUT_DIR / "per_query_type_results.csv",
        slice_rows,
        ["retrieval_mode", "query_type", "n_queries", "recall_at_5", "recall_at_10", "mrr", "ndcg_at_5", "ndcg_at_10"],
    )

    # --- per-query detail (change-level), for failure analysis ---
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
        OUTPUT_DIR / "per_query_results.csv",
        detail_rows,
        ["retrieval_mode", "query_id", "recall_at_5", "recall_at_10", "mrr"],
    )

    quadrants = failure_quadrant(gold, change_results)

    # --- print summary to console ---
    print("=== Aggregate (change-level) ===")
    for mode in MODES:
        agg = aggregate(change_results[mode])
        print(f"{mode:26s} R@5={agg['recall_at_5']:.3f} R@10={agg['recall_at_10']:.3f} "
              f"MRR={agg['mrr']:.3f} nDCG@5={agg['ndcg_at_5']:.3f} nDCG@10={agg['ndcg_at_10']:.3f}")

    print("\n=== Aggregate (evidence-level) ===")
    for mode in MODES:
        agg = aggregate(evidence_results[mode])
        print(f"{mode:26s} R@5={agg['recall_at_5']:.3f} R@10={agg['recall_at_10']:.3f} "
              f"MRR={agg['mrr']:.3f} nDCG@5={agg['ndcg_at_5']:.3f} nDCG@10={agg['ndcg_at_10']:.3f}")

    print("\n=== Per query type (change-level, Recall@5) ===")
    for query_type in query_types:
        line = f"{query_type:20s}"
        for mode in MODES:
            by_query_id = {r.query_id: r for r in change_results[mode]}
            subset = [by_query_id[q.query_id] for q in gold if q.query_type == query_type]
            line += f"  {mode}={mean([r.recall_at_5 for r in subset]):.3f}"
        print(line)

    print("\n=== Failure quadrant (change-level Recall@5, negative queries excluded) ===")
    for name, ids in quadrants.items():
        print(f"{name}: {len(ids)}  {ids}")

    print(f"\nCore change_retrieval aggregate scored over {len(gold)} queries; "
          f"{len(stability)} stability + {len(query_planner)} query_planner excluded")

    if stability:
        print("\n=== stability scope (negatives, excluded from core aggregate) ===")
        print("required_change_ids is always empty here, so change-level Recall@K is trivially 1.0 regardless of retrieval quality -- not a meaningful signal for the core aggregate.")
        for mode in MODES:
            for r in scoped_out_results[mode]:
                if r.query_id in {q.query_id for q in stability}:
                    print(f"  {mode:26s} {r.query_id}: R@5={r.recall_at_5:.3f}")

    if query_planner:
        print("\n=== query_planner scope (excluded from core aggregate) ===")
        print("required-id set is an editorial judgment call, not a single retrieval ground truth.")
        for mode in MODES:
            for r in scoped_out_results[mode]:
                if r.query_id in {q.query_id for q in query_planner}:
                    print(f"  {mode:26s} {r.query_id}: R@5={r.recall_at_5:.3f} R@10={r.recall_at_10:.3f} MRR={r.mrr:.3f}")

    print(f"\nCSV written to {OUTPUT_DIR}/")


if __name__ == "__main__":
    main()
