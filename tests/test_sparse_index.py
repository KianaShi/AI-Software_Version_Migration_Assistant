from src.retrieval.models import Chunk
from src.retrieval.sparse_index import build_sparse_index, query_sparse, tokenize

"""
Test the hand-rolled BM25 sparse index, especially the symbol-aware
tokenizer: a dotted identifier must be searchable both as a whole and by
its parts, since that's the whole point of having a sparse baseline
alongside dense (exact API/class/parameter names).
"""


def _chunk(chunk_id, text, package="foo"):
    return Chunk(
        chunk_id=chunk_id,
        text=text,
        source_document_id="doc_1",
        source_type="RELEASE_NOTE",
        provenance="test",
        package=package,
    )


def test_tokenize_keeps_dotted_symbol_whole_and_split():
    tokens = tokenize("`FooClient.create()` was removed.")

    assert "fooclient.create" in tokens
    assert "fooclient" in tokens
    assert "create" in tokens


def test_exact_symbol_query_ranks_matching_chunk_first():
    chunks = [
        _chunk("c1", "`FooClient.create()` was removed."),
        _chunk("c2", "`BarClient.build()` was renamed."),
        _chunk("c3", "General performance improvements across the library."),
    ]
    index = build_sparse_index(chunks)
    chunks_by_id = {c.chunk_id: c for c in chunks}

    results = query_sparse(index, "FooClient.create", chunks_by_id, top_k=5)

    assert results[0].chunk.chunk_id == "c1"


def test_irrelevant_chunk_is_excluded_not_just_ranked_last():
    chunks = [
        _chunk("c1", "`FooClient.create()` was removed."),
        _chunk("c2", "General performance improvements across the library."),
    ]
    index = build_sparse_index(chunks)
    chunks_by_id = {c.chunk_id: c for c in chunks}

    results = query_sparse(index, "FooClient.create", chunks_by_id, top_k=5)

    assert [r.chunk.chunk_id for r in results] == ["c1"]


def test_empty_index_returns_no_results():
    index = build_sparse_index([])

    assert query_sparse(index, "anything", {}, top_k=5) == []


def test_top_k_limits_results():
    chunks = [_chunk(f"c{i}", "FooClient.create was removed.") for i in range(5)]
    index = build_sparse_index(chunks)
    chunks_by_id = {c.chunk_id: c for c in chunks}

    results = query_sparse(index, "FooClient.create", chunks_by_id, top_k=2)

    assert len(results) == 2
