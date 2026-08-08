"""
Reciprocal Rank Fusion: combine multiple rankings using only rank
position, not raw scores (dense distances and BM25 scores aren't on
comparable scales, so fusing on rank sidesteps that entirely). One
constant, no per-source weight tuning -- the standard RRF default of
k=60 is deliberately not something to calibrate first.
"""

RRF_K = 60


def reciprocal_rank_fusion(
    rankings: list[list[str]], k: int = RRF_K
) -> list[tuple[str, float]]:
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, item_id in enumerate(ranking, start=1):
            scores[item_id] = scores.get(item_id, 0.0) + 1.0 / (k + rank)

    return sorted(scores.items(), key=lambda pair: pair[1], reverse=True)
