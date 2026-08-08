from src.retrieval.evaluation import (
    GoldQuery,
    evaluate_queries,
    mrr,
    ndcg_at_k,
    recall_at_k,
    resolve_to_change_ids,
)

"""
Test the evaluation harness's metric functions and the chunk-id ->
change-id resolution step, independent of any real retriever. The metric
functions must stay item-id-agnostic (chunk_id today, change_id if/when
Migration Chain Recall replaces plain Recall@K).
"""


def test_recall_at_k_counts_covered_required_ids():
    assert recall_at_k(["a", "b", "c"], ["a", "c"], k=3) == 1.0
    assert recall_at_k(["a"], ["a", "c"], k=3) == 0.5


def test_recall_at_k_respects_k_cutoff():
    assert recall_at_k(["x", "x", "x", "a"], ["a"], k=3) == 0.0
    assert recall_at_k(["x", "x", "x", "a"], ["a"], k=4) == 1.0


def test_recall_at_k_vacuously_true_when_nothing_required():
    assert recall_at_k(["a"], [], k=5) == 1.0


def test_mrr_is_reciprocal_of_first_hit_rank():
    assert mrr(["x", "a", "b"], ["a"]) == 0.5
    assert mrr(["a"], ["a"]) == 1.0


def test_mrr_is_zero_when_nothing_found():
    assert mrr(["x", "y"], ["a"]) == 0.0


def test_ndcg_rewards_earlier_hits_more():
    early = ndcg_at_k(["a", "x", "x"], ["a"], k=3)
    late = ndcg_at_k(["x", "x", "a"], ["a"], k=3)

    assert early == 1.0
    assert late < early


def test_resolve_to_change_ids_dedupes_and_preserves_first_occurrence_rank():
    resolver = {"c1": ["chg_a"], "c2": ["chg_a", "chg_b"], "c3": ["chg_c"]}

    resolved = resolve_to_change_ids(["c1", "c2", "c3"], resolver)

    assert resolved == ["chg_a", "chg_b", "chg_c"]


def test_resolve_to_change_ids_handles_chunks_with_no_mapping():
    resolver = {"c1": ["chg_a"]}

    resolved = resolve_to_change_ids(["c1", "unmapped_chunk"], resolver)

    assert resolved == ["chg_a"]


def test_evaluate_queries_runs_each_gold_query_through_run_query():
    gold = [
        GoldQuery(query_id="q1", query_text="anything", required_change_ids=["chg_a"]),
    ]
    resolver = {"c1": ["chg_a"]}

    results = evaluate_queries(gold, run_query=lambda text: ["c1"], chunk_to_change_ids=resolver)

    assert len(results) == 1
    assert results[0].query_id == "q1"
    assert results[0].recall_at_5 == 1.0
    assert results[0].mrr == 1.0


def test_evaluate_queries_scores_zero_when_required_change_never_retrieved():
    gold = [GoldQuery(query_id="q1", query_text="anything", required_change_ids=["chg_a"])]
    resolver = {"c1": ["chg_b"]}

    results = evaluate_queries(gold, run_query=lambda text: ["c1"], chunk_to_change_ids=resolver)

    assert results[0].recall_at_5 == 0.0
    assert results[0].mrr == 0.0
