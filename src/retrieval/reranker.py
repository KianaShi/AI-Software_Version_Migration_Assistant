from sentence_transformers import CrossEncoder

from src.retrieval.models import RetrievedChunk

"""
Stage 8B1: post-fusion reranking via a cross-encoder-style reranker
(Qwen/Qwen3-Reranker-0.6B, loaded through sentence-transformers'
CrossEncoder wrapper). Reranking is deliberately a separate step from
retrieval, not folded into retrieve_hybrid: it takes a candidate pool
the caller already retrieved/fused and reorders it by scoring each
(query, candidate_text) pair jointly -- something neither Dense (embeds
query and chunk independently, MiniLM unchanged) nor Sparse (term
overlap only) can do. Which chunks are in the candidate pool to begin
with stays entirely the caller's responsibility, same separation of
concerns as filters.apply_filters.
"""

RERANKER_MODEL_NAME = "Qwen/Qwen3-Reranker-0.6B"

_model: CrossEncoder | None = None


def _get_model() -> CrossEncoder:
    global _model
    if _model is None:
        _model = CrossEncoder(RERANKER_MODEL_NAME)
    return _model


def rerank(
    query_text: str,
    candidates: list[RetrievedChunk],
    output_k: int,
    model: CrossEncoder | None = None,
) -> list[RetrievedChunk]:
    """
    Score every candidate against query_text and return the top
    output_k, re-ranked (score/rank fields reflect the new order).
    model: injectable for testing (any object exposing
    .predict(list[tuple[str, str]]) -> Sequence[float]) -- defaults to
    the real, lazily-loaded Qwen3-Reranker-0.6B singleton.
    """
    if not candidates:
        return []

    model = model or _get_model()
    pairs = [(query_text, c.chunk.text) for c in candidates]
    scores = model.predict(pairs)

    scored = sorted(zip(candidates, scores), key=lambda pair: pair[1], reverse=True)

    return [
        RetrievedChunk(chunk=candidate.chunk, score=float(score), rank=rank)
        for rank, (candidate, score) in enumerate(scored[:output_k], start=1)
    ]
