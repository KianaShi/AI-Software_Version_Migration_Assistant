import pytest

from src.retrieval.hybrid import reciprocal_rank_fusion

"""
Test Reciprocal Rank Fusion in isolation from any real index: fusion
should reward items ranked highly across multiple sources, and must not
require every source to agree.

Stage 8B1: weights= tests below cover the ranking-ablation hook --
weights=None must stay byte-identical to the original unweighted
formula (regression safety for every pre-8B1 caller), and non-uniform
weights must be able to flip a fusion outcome deterministically.
"""


def test_item_ranked_first_in_both_lists_wins():
    fused = reciprocal_rank_fusion([["a", "b", "c"], ["a", "c", "b"]])

    assert fused[0][0] == "a"


def test_item_present_in_only_one_list_still_appears():
    fused = reciprocal_rank_fusion([["a", "b"], ["c"]])

    ids = {item_id for item_id, _ in fused}
    assert ids == {"a", "b", "c"}


def test_consistently_high_rank_beats_single_top_rank_plus_absence():
    # "b" is #2 in both lists; "a" is #1 in one list but absent from the other
    fused = reciprocal_rank_fusion([["a", "b"], ["c", "b"]])

    scores = dict(fused)
    assert scores["b"] > scores["a"]


def test_empty_rankings_produce_empty_result():
    assert reciprocal_rank_fusion([]) == []
    assert reciprocal_rank_fusion([[], []]) == []


def test_weights_none_matches_explicit_equal_weights():
    rankings = [["a", "b", "c"], ["c", "a", "b"]]

    assert reciprocal_rank_fusion(rankings) == reciprocal_rank_fusion(
        rankings, weights=[1.0, 1.0]
    )


def test_weighted_fusion_can_flip_a_tied_outcome():
    # Symmetric under equal weights ("a" #1 in list 0 / #2 in list 1,
    # "b" the mirror image) -- unweighted RRF ties them exactly.
    rankings = [["a", "b"], ["b", "a"]]
    unweighted = dict(reciprocal_rank_fusion(rankings))
    assert unweighted["a"] == unweighted["b"]

    # Weighting list 0 (where "a" is #1) higher breaks the tie in "a"'s
    # favor -- deterministic, not just "different".
    weighted = dict(reciprocal_rank_fusion(rankings, weights=[2.0, 1.0]))
    assert weighted["a"] > weighted["b"]


def test_weights_length_mismatch_raises():
    with pytest.raises(ValueError):
        reciprocal_rank_fusion([["a"], ["b"]], weights=[1.0])
