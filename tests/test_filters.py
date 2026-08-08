from src.retrieval.filters import apply_filters
from src.retrieval.models import Chunk, RetrievedChunk
from src.retrieval.version_filter import query_version_interval

"""
Test post-retrieval filtering: package filter and version-interval filter,
applied together, with ranks renumbered after filtering.
"""


def _retrieved(chunk_id, rank, package=None, version=None):
    chunk = Chunk(
        chunk_id=chunk_id,
        text="text",
        source_document_id="doc_1",
        source_type="RELEASE_NOTE",
        provenance="test",
        package=package,
        version=version,
    )
    return RetrievedChunk(chunk=chunk, score=1.0, rank=rank)


def test_package_filter_excludes_non_matching_package():
    items = [_retrieved("c1", 1, package="foo"), _retrieved("c2", 2, package="bar")]

    filtered = apply_filters(items, package="foo")

    assert [i.chunk.chunk_id for i in filtered] == ["c1"]


def test_package_filter_keeps_unknown_package():
    items = [_retrieved("c1", 1, package=None)]

    filtered = apply_filters(items, package="foo")

    assert [i.chunk.chunk_id for i in filtered] == ["c1"]


def test_version_filter_excludes_non_overlapping_chunk():
    items = [_retrieved("c1", 1, version="1.5"), _retrieved("c2", 2, version="9.0")]
    version_filter = query_version_interval("Migrate from 1.2 to 2.0.")

    filtered = apply_filters(items, version_filter=version_filter)

    assert [i.chunk.chunk_id for i in filtered] == ["c1"]


def test_version_filter_keeps_chunk_with_unknown_version():
    items = [_retrieved("c1", 1, version=None)]
    version_filter = query_version_interval("Migrate from 1.2 to 2.0.")

    filtered = apply_filters(items, version_filter=version_filter)

    assert [i.chunk.chunk_id for i in filtered] == ["c1"]


def test_ranks_are_renumbered_after_filtering():
    items = [
        _retrieved("c1", 1, package="bar"),
        _retrieved("c2", 2, package="foo"),
        _retrieved("c3", 3, package="foo"),
    ]

    filtered = apply_filters(items, package="foo")

    assert [i.rank for i in filtered] == [1, 2]
    assert [i.chunk.chunk_id for i in filtered] == ["c2", "c3"]
