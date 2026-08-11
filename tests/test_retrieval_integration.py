import chromadb

from src.extraction.sources import parse_release_note
from src.retrieval.chunking import chunk_document
from src.retrieval.dense_index import build_dense_index
from src.retrieval.evaluation import GoldQuery, evaluate_queries
from src.retrieval.retrieval import retrieve_dense, retrieve_hybrid, retrieve_sparse
from src.retrieval.sparse_index import build_sparse_index
from src.retrieval.version_filter import query_version_interval

"""
End-to-end: chunk a release note, index it dense + sparse, and compare
retrieve_dense / retrieve_sparse / retrieve_hybrid on the same corpus and
query set -- exactly the baseline comparison step 6 asks for, before any
reranker or Late Chunking would be worth adding.
"""

RELEASE_NOTE = """## v5.0.0
- `FooClient.create()` was removed.
- `BarClient.build()` was renamed to `BarClient.create()`.
- General performance improvements across the library.

## v3.0.0
- `OldThing.legacy()` was deprecated.
"""


def _build_corpus():
    doc = parse_release_note(RELEASE_NOTE)
    chunks = chunk_document(doc, default_package="foo")
    chunks_by_id = {c.chunk_id: c for c in chunks}

    client = chromadb.EphemeralClient()
    collection = client.get_or_create_collection(name="test_integration")
    build_dense_index(chunks, collection)
    sparse_index = build_sparse_index(chunks)

    return chunks_by_id, collection, sparse_index


def test_sparse_ranks_exact_symbol_query_first_even_amid_similar_prose():
    chunks_by_id, collection, sparse_index = _build_corpus()

    results = retrieve_sparse(sparse_index, "FooClient.create", chunks_by_id, output_k=1)

    assert results[0].chunk.text == "`FooClient.create()` was removed."


def test_dense_and_sparse_agree_on_top_result_for_symbol_query():
    chunks_by_id, collection, sparse_index = _build_corpus()

    dense_top = retrieve_dense(collection, "FooClient.create", chunks_by_id, output_k=1)
    sparse_top = retrieve_sparse(sparse_index, "FooClient.create", chunks_by_id, output_k=1)

    assert dense_top[0].chunk.chunk_id == sparse_top[0].chunk.chunk_id


def test_hybrid_returns_results_present_in_dense_or_sparse():
    chunks_by_id, collection, sparse_index = _build_corpus()

    dense_ids = {r.chunk.chunk_id for r in retrieve_dense(collection, "FooClient.create", chunks_by_id, output_k=4)}
    sparse_ids = {r.chunk.chunk_id for r in retrieve_sparse(sparse_index, "FooClient.create", chunks_by_id, output_k=4)}
    hybrid_ids = {r.chunk.chunk_id for r in retrieve_hybrid(collection, sparse_index, "FooClient.create", chunks_by_id, output_k=4)}

    assert hybrid_ids <= (dense_ids | sparse_ids)
    assert hybrid_ids  # non-empty


def test_hybrid_weights_none_matches_default_unweighted_fusion():
    chunks_by_id, collection, sparse_index = _build_corpus()

    default = retrieve_hybrid(collection, sparse_index, "FooClient.create", chunks_by_id, output_k=4)
    explicit_none = retrieve_hybrid(collection, sparse_index, "FooClient.create", chunks_by_id, output_k=4, weights=None)
    explicit_equal = retrieve_hybrid(collection, sparse_index, "FooClient.create", chunks_by_id, output_k=4, weights=(1.0, 1.0))

    ids = lambda results: [r.chunk.chunk_id for r in results]
    assert ids(default) == ids(explicit_none) == ids(explicit_equal)


def test_extreme_dense_weight_converges_on_dense_only_ranking():
    # Mathematically guaranteed regardless of corpus specifics: as the
    # dense weight dominates the sparse weight, each pair's RRF score
    # difference is dominated by their dense-rank difference (ranks are
    # a tie-free permutation), so the fused order must converge on
    # dense-only's own order -- a wiring test that retrieve_hybrid's
    # weights= actually reaches reciprocal_rank_fusion, not just a
    # plausible-looking ranking shuffle.
    chunks_by_id, collection, sparse_index = _build_corpus()

    dense_heavy = retrieve_hybrid(
        collection, sparse_index, "FooClient.create", chunks_by_id, output_k=4, weights=(1e6, 1e-6)
    )
    dense_only = retrieve_dense(collection, "FooClient.create", chunks_by_id, output_k=4)

    assert [r.chunk.chunk_id for r in dense_heavy] == [r.chunk.chunk_id for r in dense_only]


def test_version_filter_applies_identically_across_all_three_modes():
    chunks_by_id, collection, sparse_index = _build_corpus()
    version_filter = query_version_interval("as of 5.0")

    for retrieved in (
        retrieve_dense(collection, "was deprecated", chunks_by_id, output_k=5, version_filter=version_filter),
        retrieve_sparse(sparse_index, "was deprecated", chunks_by_id, output_k=5, version_filter=version_filter),
        retrieve_hybrid(collection, sparse_index, "was deprecated", chunks_by_id, output_k=5, version_filter=version_filter),
    ):
        assert all(item.chunk.version == "5.0.0" for item in retrieved)


def test_evaluate_queries_compares_dense_sparse_hybrid_on_same_gold_set():
    chunks_by_id, collection, sparse_index = _build_corpus()

    target_chunk_id = next(
        c.chunk_id for c in chunks_by_id.values() if c.text == "`FooClient.create()` was removed."
    )
    chunk_to_change_ids = {target_chunk_id: ["chg_foo_create_removed"]}
    gold = [
        GoldQuery(
            query_id="q1",
            query_text="FooClient.create",
            required_change_ids=["chg_foo_create_removed"],
        )
    ]

    def run(query_text, retrieve_fn):
        return [r.chunk.chunk_id for r in retrieve_fn(query_text)]

    dense_results = evaluate_queries(
        gold,
        run_query=lambda q: run(q, lambda t: retrieve_dense(collection, t, chunks_by_id, output_k=5)),
        chunk_to_change_ids=chunk_to_change_ids,
    )
    sparse_results = evaluate_queries(
        gold,
        run_query=lambda q: run(q, lambda t: retrieve_sparse(sparse_index, t, chunks_by_id, output_k=5)),
        chunk_to_change_ids=chunk_to_change_ids,
    )
    hybrid_results = evaluate_queries(
        gold,
        run_query=lambda q: run(
            q, lambda t: retrieve_hybrid(collection, sparse_index, t, chunks_by_id, output_k=5)
        ),
        chunk_to_change_ids=chunk_to_change_ids,
    )

    for results in (dense_results, sparse_results, hybrid_results):
        assert results[0].recall_at_5 == 1.0
