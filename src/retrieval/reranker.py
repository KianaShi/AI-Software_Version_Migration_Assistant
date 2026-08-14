import math
from typing import Protocol, Sequence

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


class Reranker(Protocol):
    """The real contract rerank() needs -- CrossEncoder satisfies it
    structurally, but so does any test stub with a matching predict(),
    without either having to subclass the other."""

    def predict(self, pairs: list[tuple[str, str]]) -> Sequence[float]: ...


RERANKER_MODEL_NAME = "Qwen/Qwen3-Reranker-0.6B"
# Pinned so a re-run can't silently pick up a newer upload to this model
# name -- reused verbatim (not re-hardcoded) wherever reranker
# reproducibility needs to be reported, e.g. scripts/run_ranking_ablation.py.
RERANKER_MODEL_REVISION = "e61197ed45024b0ed8a2d74b80b4d909f1255473"

_model: CrossEncoder | None = None


def _get_model() -> CrossEncoder:
    global _model
    if _model is None:
        _model = CrossEncoder(RERANKER_MODEL_NAME, revision=RERANKER_MODEL_REVISION)
    return _model


def rerank(
    query_text: str,
    candidates: list[RetrievedChunk],
    output_k: int,
    model: Reranker | None = None,
) -> list[RetrievedChunk]:
    """
    Score every candidate against query_text and return the top
    output_k, re-ranked (score/rank fields reflect the new order).
    model: injectable for testing (any object satisfying the Reranker
    protocol) -- defaults to the real, lazily-loaded Qwen3-Reranker-0.6B
    singleton.
    """
    if output_k < 0:
        raise ValueError(f"output_k ({output_k}) must not be negative.")
    if output_k == 0 or not candidates:
        return []

    model = model if model is not None else _get_model()
    pairs = [(query_text, c.chunk.text) for c in candidates]
    scores = model.predict(pairs)

    if len(scores) != len(candidates):
        raise ValueError(
            f"model.predict() returned {len(scores)} scores for {len(candidates)} "
            "candidates -- a reranker model must return exactly one score per candidate."
        )

    float_scores = [float(s) for s in scores]
    for s in float_scores:
        if not math.isfinite(s):
            raise ValueError(
                f"model.predict() returned a non-finite score ({s!r}) -- reranker "
                "scores must be finite to sort meaningfully."
            )

    scored = sorted(zip(candidates, float_scores), key=lambda pair: pair[1], reverse=True)

    return [
        RetrievedChunk(chunk=candidate.chunk, score=score, rank=rank)
        for rank, (candidate, score) in enumerate(scored[:output_k], start=1)
    ]
