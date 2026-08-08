from src.retrieval.hybrid import reciprocal_rank_fusion

"""
Test Reciprocal Rank Fusion in isolation from any real index: fusion
should reward items ranked highly across multiple sources, and must not
require every source to agree.
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
