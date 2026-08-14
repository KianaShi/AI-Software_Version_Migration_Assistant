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

Stage 8B0: candidate_k (how many ranked candidates are fetched/fused
before filtering) is a fixed pool size, independent of output_k (how
many of those survive as the final result). Previously fetch_k scaled
with the caller's top_k (fetch_k = top_k * 4), so calling the same
retriever with different top_k values queried genuinely different
candidate pools. That's harmless for Dense/Sparse alone (a wider
single-source pool only appends lower-ranked candidates after the ones
a narrower pool already had -- their relative order and filtering never
changes), but not for Hybrid: RRF only scores candidates that appear in
at least one fetched list, so a chunk absent from a narrower pool
contributes zero score from that side, and admitting it at a wider pool
can outrank chunks that were already near the top -- not just extend the
list, reorder it (this is the exact mechanism behind the Stage 8A
q_multi_02 pool-size artifact documented in
scripts/diagnose_failed_queries.py). That meant Top5 from one call and
Top10 from another weren't guaranteed to be slices of "the same ranking"
at all.

Now every call fetches/fuses over the same CANDIDATE_K-sized pool
regardless of output_k; output_k only slices the already-computed,
already-filtered result. Top5/Top10/Top20 (for output_k <= CANDIDATE_K)
are therefore guaranteed prefixes of one identical ranking, by
construction of list slicing over an unchanging list -- see
tests/test_retrieval_prefix_stability.py.
"""

CANDIDATE_K = 40


def _check_output_k(output_k: int, candidate_k: int) -> None:
    if candidate_k <= 0:
        # fetch_k=0 is falsy, so query_dense/query_sparse would silently
        # fall back to their own top_k=10 default instead of an empty
        # pool -- exactly the "candidate pool secretly depends on
        # something other than candidate_k" failure this stage exists to
        # prevent, so reject it explicitly rather than let it happen.
        raise ValueError(f"candidate_k ({candidate_k}) must be positive.")
    if output_k < 0:
        raise ValueError(f"output_k ({output_k}) must not be negative.")
    if output_k > candidate_k:
        raise ValueError(
            f"output_k ({output_k}) cannot exceed candidate_k ({candidate_k}) -- "
            "widen candidate_k explicitly if you need a deeper result."
        )


def retrieve_dense(
    collection,
    query_text: str,
    chunks_by_id: dict[str, Chunk],
    output_k: int = 10,
    candidate_k: int = CANDIDATE_K,
    package: str | None = None,
    version_filter: VersionInterval | None = None,
) -> list[RetrievedChunk]:
    _check_output_k(output_k, candidate_k)
    raw = query_dense(collection, query_text, chunks_by_id, fetch_k=candidate_k)
    filtered = apply_filters(raw, package=package, version_filter=version_filter)
    return filtered[:output_k]


def retrieve_sparse(
    index,
    query_text: str,
    chunks_by_id: dict[str, Chunk],
    output_k: int = 10,
    candidate_k: int = CANDIDATE_K,
    package: str | None = None,
    version_filter: VersionInterval | None = None,
) -> list[RetrievedChunk]:
    _check_output_k(output_k, candidate_k)
    raw = query_sparse(index, query_text, chunks_by_id, fetch_k=candidate_k)
    filtered = apply_filters(raw, package=package, version_filter=version_filter)
    return filtered[:output_k]


def retrieve_hybrid(
    collection,
    sparse_index,
    query_text: str,
    chunks_by_id: dict[str, Chunk],
    output_k: int = 10,
    candidate_k: int = CANDIDATE_K,
    package: str | None = None,
    version_filter: VersionInterval | None = None,
    weights: tuple[float, float] | None = None,
) -> list[RetrievedChunk]:
    """
    weights: optional (dense_weight, sparse_weight) passed through to
    reciprocal_rank_fusion -- Stage 8B1 ablation hook. None (default)
    reproduces the exact unweighted 1:1 fusion this function always had.
    """
    _check_output_k(output_k, candidate_k)
    dense_raw = query_dense(collection, query_text, chunks_by_id, fetch_k=candidate_k)
    sparse_raw = query_sparse(sparse_index, query_text, chunks_by_id, fetch_k=candidate_k)

    dense_ranking = [r.chunk.chunk_id for r in dense_raw]
    sparse_ranking = [r.chunk.chunk_id for r in sparse_raw]
    fused = reciprocal_rank_fusion(
        [dense_ranking, sparse_ranking],
        weights=list(weights) if weights is not None else None,
    )

    combined = [
        RetrievedChunk(chunk=chunks_by_id[chunk_id], score=score, rank=rank)
        for rank, (chunk_id, score) in enumerate(fused, start=1)
        if chunk_id in chunks_by_id
    ]
    filtered = apply_filters(combined, package=package, version_filter=version_filter)
    return filtered[:output_k]
