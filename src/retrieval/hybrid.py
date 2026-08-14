"""
Reciprocal Rank Fusion: combine multiple rankings using only rank
position, not raw scores (dense distances and BM25 scores aren't on
comparable scales, so fusing on rank sidesteps that entirely). RRF_K
stays the standard default (60), not something ablated here.

Stage 8B1: per-ranking weights are now supported (`weights`, default
None), so Dense:BM25 contribution can be scaled independently of
`RRF_K` -- e.g. weights=[2.0, 1.0] doubles every rank position's score
contribution from the first ranking before summing. `weights=None`
reproduces the exact unweighted formula this function always had
(every list contributes at weight 1.0), so every existing caller that
doesn't pass `weights` is byte-for-byte unaffected.
"""

RRF_K = 60


def reciprocal_rank_fusion(
    rankings: list[list[str]], k: int = RRF_K, weights: list[float] | None = None
) -> list[tuple[str, float]]:
    if weights is None:
        weights = [1.0] * len(rankings)
    if len(weights) != len(rankings):
        raise ValueError(
            f"weights has {len(weights)} entries but rankings has {len(rankings)}"
        )

    scores: dict[str, float] = {}
    for ranking, weight in zip(rankings, weights):
        for rank, item_id in enumerate(ranking, start=1):
            scores[item_id] = scores.get(item_id, 0.0) + weight / (k + rank)

    return sorted(scores.items(), key=lambda pair: pair[1], reverse=True)
