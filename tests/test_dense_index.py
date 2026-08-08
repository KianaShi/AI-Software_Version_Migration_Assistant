import chromadb

from src.retrieval.dense_index import build_dense_index, query_dense
from src.retrieval.models import Chunk

"""
Test the dense retrieval baseline. Uses an EphemeralClient collection
(as tests/test_vector_store.py does) rather than the persistent
chroma_db/ path, so tests don't leave real index files behind.
"""


def _chunk(chunk_id, text, **kwargs):
    return Chunk(
        chunk_id=chunk_id,
        text=text,
        source_document_id="doc_1",
        source_type="RELEASE_NOTE",
        provenance="test",
        **kwargs,
    )


def _collection(name):
    client = chromadb.EphemeralClient()
    return client.get_or_create_collection(name=name)


def test_build_and_query_returns_expected_chunk_ids():
    chunks = [
        _chunk("c1", "The office opens at 9 AM."),
        _chunk("c2", "Employees receive 15 vacation days."),
    ]
    collection = _collection("test_dense_basic")
    build_dense_index(chunks, collection)
    chunks_by_id = {c.chunk_id: c for c in chunks}

    results = query_dense(collection, "When does the office open?", chunks_by_id, top_k=2)

    assert {r.chunk.chunk_id for r in results} == {"c1", "c2"}
    assert results[0].chunk.chunk_id == "c1"


def test_query_uses_custom_chunk_ids_not_derived_ids():
    chunks = [_chunk("my_custom_id", "Some content about clients.")]
    collection = _collection("test_dense_custom_ids")
    build_dense_index(chunks, collection)
    chunks_by_id = {c.chunk_id: c for c in chunks}

    results = query_dense(collection, "clients", chunks_by_id, top_k=1)

    assert results[0].chunk.chunk_id == "my_custom_id"


def test_metadata_is_stored_and_queryable_via_where():
    chunks = [
        _chunk("c1", "FooClient content.", package="foo", version="5.0"),
        _chunk("c2", "BarClient content.", package="bar", version="3.0"),
    ]
    collection = _collection("test_dense_metadata")
    build_dense_index(chunks, collection)

    result = collection.get(where={"package": "foo"})

    assert result["ids"] == ["c1"]


def test_empty_chunk_list_does_not_error():
    collection = _collection("test_dense_empty")

    build_dense_index([], collection)

    assert collection.count() == 0
