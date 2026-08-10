import chromadb
import pytest

from src.retrieval.dense_index import build_dense_index
from src.retrieval.models import Chunk
from src.retrieval.retrieval import CANDIDATE_K, retrieve_dense, retrieve_hybrid, retrieve_sparse
from src.retrieval.sparse_index import build_sparse_index

"""
Stage 8B0 regression: retrieve_dense/sparse/hybrid must fetch/fuse over
the same fixed candidate_k pool regardless of output_k, so the same
query sliced at output_k=5/10/20 always returns nested prefixes of one
ranking -- not three independently-pooled rankings that only happen to
overlap. This is the exact property that was broken before Stage 8B0
for retrieve_hybrid (RRF's candidate pool used to scale with output_k),
and is what makes Top5/Top10/Top20 comparable at all.

A corpus of 25 chunks (more than the largest output_k exercised here)
all sharing the query's terms, so both Dense and BM25 return at least
20 non-zero candidates each -- this test only checks the *structural*
nesting property, not ranking quality, so relevance doesn't need to
vary across chunks for it to be meaningful.
"""

N_CHUNKS = 25
QUERY = "pydantic migration guide"


def _build_corpus():
    chunks = [
        Chunk(
            chunk_id=f"chunk_{i:02d}",
            text=f"`Thing{i:02d}.method()` was removed as part of the pydantic migration guide overhaul.",
            source_document_id="doc",
            source_type="release_note",
            provenance="test",
        )
        for i in range(N_CHUNKS)
    ]
    chunks_by_id = {c.chunk_id: c for c in chunks}

    client = chromadb.EphemeralClient()
    collection = client.get_or_create_collection(name="test_prefix_stability")
    build_dense_index(chunks, collection)
    sparse_index = build_sparse_index(chunks)

    return chunks_by_id, collection, sparse_index


def _ids(results):
    return [r.chunk.chunk_id for r in results]


def _run(retrieve_kind, output_k, chunks_by_id, collection, sparse_index):
    if retrieve_kind == "dense":
        return _ids(retrieve_dense(collection, QUERY, chunks_by_id, output_k=output_k))
    if retrieve_kind == "sparse":
        return _ids(retrieve_sparse(sparse_index, QUERY, chunks_by_id, output_k=output_k))
    return _ids(retrieve_hybrid(collection, sparse_index, QUERY, chunks_by_id, output_k=output_k))


@pytest.mark.parametrize("retrieve_kind", ["dense", "sparse", "hybrid"])
def test_top5_top10_top20_are_nested_prefixes(retrieve_kind):
    chunks_by_id, collection, sparse_index = _build_corpus()

    top5 = _run(retrieve_kind, 5, chunks_by_id, collection, sparse_index)
    top10 = _run(retrieve_kind, 10, chunks_by_id, collection, sparse_index)
    top20 = _run(retrieve_kind, 20, chunks_by_id, collection, sparse_index)

    assert len(top5) == 5
    assert len(top10) == 10
    assert len(top20) == 20
    assert top10[:5] == top5
    assert top20[:10] == top10


@pytest.mark.parametrize("retrieve_kind", ["dense", "sparse", "hybrid"])
def test_output_k_greater_than_candidate_k_raises(retrieve_kind):
    chunks_by_id, collection, sparse_index = _build_corpus()

    with pytest.raises(ValueError):
        if retrieve_kind == "dense":
            retrieve_dense(collection, QUERY, chunks_by_id, output_k=50, candidate_k=CANDIDATE_K)
        elif retrieve_kind == "sparse":
            retrieve_sparse(sparse_index, QUERY, chunks_by_id, output_k=50, candidate_k=CANDIDATE_K)
        else:
            retrieve_hybrid(collection, sparse_index, QUERY, chunks_by_id, output_k=50, candidate_k=CANDIDATE_K)


@pytest.mark.parametrize("retrieve_kind", ["dense", "sparse", "hybrid"])
def test_candidate_k_zero_or_negative_raises(retrieve_kind):
    # candidate_k=0 is a real footgun, not just an edge case: fetch_k=0 is
    # falsy, so query_dense/query_sparse's `fetch_k or top_k` would
    # silently fall back to their own top_k=10 default instead of an
    # empty pool -- exactly the "pool secretly depends on something other
    # than candidate_k" bug this stage exists to prevent.
    chunks_by_id, collection, sparse_index = _build_corpus()

    with pytest.raises(ValueError):
        if retrieve_kind == "dense":
            retrieve_dense(collection, QUERY, chunks_by_id, output_k=0, candidate_k=0)
        elif retrieve_kind == "sparse":
            retrieve_sparse(sparse_index, QUERY, chunks_by_id, output_k=0, candidate_k=0)
        else:
            retrieve_hybrid(collection, sparse_index, QUERY, chunks_by_id, output_k=0, candidate_k=0)


@pytest.mark.parametrize("retrieve_kind", ["dense", "sparse", "hybrid"])
def test_output_k_negative_raises(retrieve_kind):
    chunks_by_id, collection, sparse_index = _build_corpus()

    with pytest.raises(ValueError):
        if retrieve_kind == "dense":
            retrieve_dense(collection, QUERY, chunks_by_id, output_k=-1, candidate_k=CANDIDATE_K)
        elif retrieve_kind == "sparse":
            retrieve_sparse(sparse_index, QUERY, chunks_by_id, output_k=-1, candidate_k=CANDIDATE_K)
        else:
            retrieve_hybrid(collection, sparse_index, QUERY, chunks_by_id, output_k=-1, candidate_k=CANDIDATE_K)


def test_default_candidate_k_is_40():
    assert CANDIDATE_K == 40


def test_widening_candidate_k_explicitly_allows_deeper_output_k():
    chunks_by_id, collection, _ = _build_corpus()

    results = retrieve_dense(collection, QUERY, chunks_by_id, output_k=25, candidate_k=25)

    assert len(results) == 25
