from src.retrieval.dense_index import query_dense
from src.retrieval.filters import apply_filters
from src.retrieval.hybrid import reciprocal_rank_fusion
from src.retrieval.models import Chunk, RetrievedChunk
from src.retrieval.sparse_index import query_sparse
from src.retrieval.version_filter import VersionInterval

"""
Top-level retrieval entrypoints: retrieve_dense / retrieve_sparse /
retrieve_hybrid share the same signature and the same post-filtering
(filters.apply_filters), so evaluation.py can swap between them to
compare Dense vs. Sparse vs. Hybrid under identical conditions -- the
whole point of building a baseline before adding a reranker or Late
Chunking.

fetch_k defaults to 4x top_k: filtering happens after ranking, so
retrieving only top_k candidates and then filtering could leave fewer
than top_k results even when enough exist further down the ranking.
"""

_FETCH_MULTIPLIER = 4


def retrieve_dense(
    collection,
    query_text: str,
    chunks_by_id: dict[str, Chunk],
    top_k: int = 10,
    package: str | None = None,
    version_filter: VersionInterval | None = None,
) -> list[RetrievedChunk]:
    raw = query_dense(collection, query_text, chunks_by_id, fetch_k=top_k * _FETCH_MULTIPLIER)
    filtered = apply_filters(raw, package=package, version_filter=version_filter)
    return filtered[:top_k]


def retrieve_sparse(
    index,
    query_text: str,
    chunks_by_id: dict[str, Chunk],
    top_k: int = 10,
    package: str | None = None,
    version_filter: VersionInterval | None = None,
) -> list[RetrievedChunk]:
    raw = query_sparse(index, query_text, chunks_by_id, fetch_k=top_k * _FETCH_MULTIPLIER)
    filtered = apply_filters(raw, package=package, version_filter=version_filter)
    return filtered[:top_k]


def retrieve_hybrid(
    collection,
    sparse_index,
    query_text: str,
    chunks_by_id: dict[str, Chunk],
    top_k: int = 10,
    package: str | None = None,
    version_filter: VersionInterval | None = None,
) -> list[RetrievedChunk]:
    fetch_k = top_k * _FETCH_MULTIPLIER
    dense_raw = query_dense(collection, query_text, chunks_by_id, fetch_k=fetch_k)
    sparse_raw = query_sparse(sparse_index, query_text, chunks_by_id, fetch_k=fetch_k)

    dense_ranking = [r.chunk.chunk_id for r in dense_raw]
    sparse_ranking = [r.chunk.chunk_id for r in sparse_raw]
    fused = reciprocal_rank_fusion([dense_ranking, sparse_ranking])

    combined = [
        RetrievedChunk(chunk=chunks_by_id[chunk_id], score=score, rank=rank)
        for rank, (chunk_id, score) in enumerate(fused, start=1)
        if chunk_id in chunks_by_id
    ]
    filtered = apply_filters(combined, package=package, version_filter=version_filter)
    return filtered[:top_k]
